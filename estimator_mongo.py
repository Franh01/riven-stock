"""Datos y publicación de la calibración en Mongo (lo que corre en la nube).

El armado de los casos es el mismo del backtest: para cada venta se reconstruye
el mercado que había cuando se detectó (publicaciones activas de esa arma, sin
las del vendedor) y se pide el estimado con el pricing de la app.

Sin la app: sólo stdlib + pymongo, así entra en la Lambda.
"""
import datetime as dt
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SINCE_DAYS = 14
WINDOW_H = 6            # horas de tolerancia para considerar viva una publicación
MAX_SALES = 20000
COL = "estimator"

import pricing  # noqa: E402


def uri():
    if os.environ.get("MONGODB_URI"):
        return os.environ["MONGODB_URI"]
    for line in (ROOT / "cloud" / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("MONGODB_URI="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("Falta MONGODB_URI")


def db(client=None):
    from pymongo import MongoClient
    return db_client(client).get_default_database()


def db_client(client=None):
    from pymongo import MongoClient
    return client or MongoClient(uri(), serverSelectionTimeoutMS=20000)


def _iso(v):
    """Fecha de creación en ISO (pricing la usa para castigar publicaciones viejas)."""
    if not v:
        return None
    try:
        return dt.datetime.fromtimestamp(_ts(v), dt.timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def _ts(v):
    if isinstance(v, dt.datetime):
        t = v
    else:
        t = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.timestamp()


def fetch_rtypes():
    """Tipo de riven por arma desde la API pública. {} si no hay red."""
    try:
        import urllib.request
        req = urllib.request.Request("https://api.warframe.market/v2/riven/weapons",
                                     headers={"User-Agent": "riven-stock-estimator", "accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())["data"]
        return {w["slug"]: w.get("rivenType") for w in data}
    except Exception:  # noqa: BLE001 -- sin tipos el estimado sale algo peor, pero sale
        return {}


def stored_rtypes(collection):
    return (collection.find_one({"_id": "rtypes"}) or {}).get("data") or {}


def cases_from_mongo(limit=MAX_SALES, since_days=SINCE_DAYS, client=None):
    """[(arma, tipo, t, error_log)] con las ventas inferidas de los últimos días."""
    database = db(client)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=since_days)
    q = {"suspect": {"$exists": False}, "price": {"$gt": 0},
         "detected_at": {"$gte": since.replace(tzinfo=None)}, "confidence": {"$in": ["alta", "media"]}}
    proj = {"_id": 0, "weapon": 1, "price": 1, "attrs": 1, "rolls": 1, "rank": 1, "seller": 1, "detected_at": 1}
    sales = list(database.sales.find(q, proj).sort("detected_at", -1).limit(limit))
    if not sales:
        return []
    tipos = fetch_rtypes() or stored_rtypes(database[COL])
    weapons = sorted({s["weapon"] for s in sales})
    lproj = {"weapon": 1, "attrs": 1, "rolls": 1, "rank": 1, "seller": 1, "price_last": 1,
             "status_last": 1, "created": 1, "first_seen": 1, "last_seen": 1}
    start = (since - dt.timedelta(days=2)).replace(tzinfo=None)
    listings = {}
    for d in database.listings.find({"weapon": {"$in": weapons}, "last_seen": {"$gte": start}}, lproj):
        listings.setdefault(d["weapon"], []).append({
            "id": str(d["_id"]), "p": d.get("price_last"), "st": d.get("status_last"), "s": d["attrs"],
            "r": d.get("rolls") or 0, "k": d.get("rank"), "nm": d.get("seller"),
            "c": _iso(d.get("created")), "fs": _ts(d["first_seen"]), "ls": _ts(d["last_seen"])})
    out = []
    for s in sales:
        t = _ts(s["detected_at"])
        market = [o for o in listings.get(s["weapon"], []) if o["p"] and o["fs"] <= t
                  and o["ls"] >= t - WINDOW_H * 3600 and o["nm"] != s.get("seller")]
        if not market:
            continue
        view = {"stats": [{"slug": a, "value": v, "positive": p} for a, v, p in s["attrs"]],
                "rolls": s.get("rolls") or 0, "rank": s.get("rank")}
        rtype = tipos.get(s["weapon"])
        est = pricing.estimate(view, market, rtype=rtype, weapon=s["weapon"])
        if not est or not est.get("price"):
            continue
        out.append((s["weapon"], rtype, t, round(math.log(est["price"] / s["price"]), 6)))
    return out


def save(doc, rtypes_map=None, client=None):
    """Publica los factores (un solo documento, el que lee la API) y los tipos usados."""
    database = db(client)
    col = database[COL]
    col.replace_one({"_id": "factors"}, {**doc, "_id": "factors"}, upsert=True)
    if rtypes_map:
        col.replace_one({"_id": "rtypes"}, {"_id": "rtypes", "data": rtypes_map,
                                            "updated": doc.get("updated")}, upsert=True)
    if doc.get("updated"):
        col.replace_one({"_id": f"h:{doc['updated']}"},
                        {"_id": f"h:{doc['updated']}", "at": doc["updated"],
                         "validated": doc.get("validated"), "niveles": {k: len(v) for k, v in doc["factors"].items()}},
                        upsert=True)
    return doc
