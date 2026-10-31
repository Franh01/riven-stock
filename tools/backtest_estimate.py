"""Backtest del precio estimado contra ventas inferidas reales (Mongo, solo lectura).

Para cada venta arma el mercado que había en ese momento (publicaciones del arma vistas activas
alrededor de la venta, sin la del vendedor), corre pricing.estimate y mide el error en escala log.

  python tools/backtest_estimate.py export [--days 14] [--n 4000]   # baja datos a cache/backtest.json
  python tools/backtest_estimate.py run                             # mide con el pricing.py actual

export necesita pymongo y MONGODB_URI (variable de entorno o cloud/.env).
"""
import argparse
import datetime as dt
import json
import math
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CACHE = ROOT / "cache" / "backtest.json"
FMT = "%Y-%m-%d %H:%M:%S"


def _ts(v):
    """Fecha de Mongo (datetime o texto) -> segundos UTC."""
    if isinstance(v, dt.datetime):
        t = v
    else:
        t = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.timestamp()


def _uri():
    if os.environ.get("MONGODB_URI"):
        return os.environ["MONGODB_URI"]
    for line in (ROOT / "cloud" / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("MONGODB_URI="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("Falta MONGODB_URI")


def export(days, n, seed=7):
    import requests
    from pymongo import MongoClient
    from wfm_client import HEADERS
    res = requests.get("https://api.warframe.market/v2/riven/weapons", headers=HEADERS, timeout=20)
    res.raise_for_status()
    rtypes = {w["slug"]: w.get("rivenType") for w in res.json()["data"]}
    db = MongoClient(_uri(), serverSelectionTimeoutMS=20000).get_default_database()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    q = {"suspect": {"$exists": False}, "price": {"$gt": 0}, "detected_at": {"$gte": since.replace(tzinfo=None)}}
    proj = {"_id": 0, "weapon": 1, "price": 1, "attrs": 1, "rolls": 1, "rank": 1, "seller": 1, "detected_at": 1}
    sales = list(db.sales.find(q, proj))
    random.Random(seed).shuffle(sales)
    sales = sales[:n]
    weapons = sorted({s["weapon"] for s in sales})
    print(f"PROGRESS 1/3\n{len(sales)} ventas de {len(weapons)} armas", flush=True)
    lproj = {"_id": 1, "weapon": 1, "attrs": 1, "rolls": 1, "rank": 1, "seller": 1, "price_last": 1,
             "status_last": 1, "first_seen": 1, "last_seen": 1}
    listings = {}
    start = since - dt.timedelta(days=2)
    for d in db.listings.find({"weapon": {"$in": weapons}, "last_seen": {"$gte": start.replace(tzinfo=None)}}, lproj):
        listings.setdefault(d["weapon"], []).append({
            "id": str(d["_id"]), "p": d.get("price_last"), "st": d.get("status_last"), "s": d["attrs"],
            "r": d.get("rolls") or 0, "k": d.get("rank"), "nm": d.get("seller"),
            "fs": _ts(d["first_seen"]), "ls": _ts(d["last_seen"])})
    print("PROGRESS 2/3", flush=True)
    out = {"sales": [{**{k: v for k, v in s.items() if k != "detected_at"}, "t": _ts(s["detected_at"])}
                      for s in sales], "listings": listings, "rtypes": rtypes}
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(out), encoding="utf-8")
    print(f"PROGRESS 3/3\n{sum(map(len, listings.values()))} publicaciones -> {CACHE}", flush=True)


def market_at(listings, sale, window_h=6):
    """Publicaciones activas cuando se detectó la venta (sin las del vendedor)."""
    t = sale["t"]
    return [o for o in listings if o["p"] and o["fs"] <= t and o["ls"] >= t - window_h * 3600
            and o["nm"] != sale.get("seller")]


def cases(data):
    """[(venta, view, mercado, rtype)] con al menos una publicación de referencia."""
    out = []
    for s in data["sales"]:
        market = market_at(data["listings"].get(s["weapon"], []), s)
        if not market:
            continue
        view = {"stats": [{"slug": a, "value": v, "positive": p} for a, v, p in s["attrs"]],
                "rolls": s.get("rolls") or 0, "rank": s.get("rank")}
        out.append((s, view, market, data["rtypes"].get(s["weapon"])))
    return out


def bucket(n):
    return "1-2" if n <= 2 else "3-5" if n <= 5 else "6-11" if n <= 11 else "12"


def summarize(rows):
    """rows: [(clave, err_log)] -> {clave: (n, mediana |err|, % dentro de x1.5, sesgo)}"""
    by = {}
    for k, e in rows:
        by.setdefault(k, []).append(e)
    res = {}
    for k, es in sorted(by.items()):
        a = sorted(abs(e) for e in es)
        b = sorted(es)
        res[k] = (len(es), a[len(a) // 2], sum(x <= math.log(1.5) for x in a) / len(a), b[len(b) // 2])
    return res


def run(estimate=None):
    import pricing
    estimate = estimate or pricing.estimate
    data = json.loads(CACHE.read_text(encoding="utf-8"))
    cs = cases(data)
    rows, missing = [], 0
    total = len(cs)
    print(f"PROGRESS 0/{total}", flush=True)
    for i, (s, view, market, rtype) in enumerate(cs, 1):
        est = estimate(view, market, rtype=rtype, weapon=s["weapon"])
        if not est or not est.get("price"):
            missing += 1
        else:
            e = math.log(est["price"] / s["price"])
            rows += [(bucket(est["n"]), e), (est["confidence"], e), ("TOTAL", e)]
        if i % 500 == 0:
            print(f"PROGRESS {i}/{total}", flush=True)
    print(f"PROGRESS {total}/{total}")
    print(f"{total} ventas con mercado, {missing} sin estimado")
    print(f"{'grupo':>6} {'n':>6} {'med|err|':>9} {'<=x1.5':>7} {'sesgo':>7}")
    for k, (n, med, ok, bias) in summarize(rows).items():
        print(f"{k:>6} {n:>6} {math.exp(med):>8.2f}x {ok * 100:>6.1f}% {math.exp(bias):>6.2f}x")
    return rows, missing


def calibrate(estimate=None, train_frac=0.7):
    """Ajusta los factores por arma con las ventas viejas y mide la mejora en las nuevas.

    La división es temporal, no por arma: el factor se aplica justamente a las armas
    que tienen historial, así que lo honesto es entrenar con lo que había antes de T
    y medir en lo que vino después."""
    import calibration
    import pricing
    estimate = estimate or pricing.estimate
    data = json.loads(CACHE.read_text(encoding="utf-8"))
    cs = cases(data)
    rows = []
    total = len(cs)
    print(f"PROGRESS 0/{total}", flush=True)
    for i, (s, view, market, rtype) in enumerate(cs, 1):
        est = estimate(view, market, rtype=rtype, weapon=s["weapon"])
        if est and est.get("price"):
            rows.append((s["weapon"], s["t"], math.log(est["price"] / s["price"])))
        if i % 500 == 0:
            print(f"PROGRESS {i}/{total}", flush=True)
    print(f"PROGRESS {total}/{total}")
    rows.sort(key=lambda r: r[1])
    cut = rows[int(len(rows) * train_frac)][1]
    samples = {}
    for w, t, e in rows:
        if t < cut:
            samples.setdefault(w, []).append(e)
    factors = calibration.fit(samples)
    test = [r for r in rows if r[1] >= cut]
    before = summarize([("antes", e) for _, _, e in test])["antes"]
    after = summarize([("despues", e + math.log(factors[w]["f"])) if w in factors else ("despues", e)
                       for w, _, e in test])["despues"]
    cubiertas = sum(1 for w, _, _ in test if w in factors)
    print(f"{len(rows)} ventas con estimado; corte {dt.datetime.fromtimestamp(cut, dt.timezone.utc):%Y-%m-%d %H:%M} UTC")
    print(f"factores para {len(factors)} armas; en la prueba entran {cubiertas} ventas de armas calibradas")
    for nombre, (n, med, ok, bias) in (("antes", before), ("despues", after)):
        print(f"{nombre:>8} {n:>6} {math.exp(med):>8.2f}x {ok * 100:>6.1f}% {math.exp(bias):>6.2f}x")
    top = sorted(factors.items(), key=lambda kv: -abs(math.log(kv[1]["f"])))[:8]
    for w, e in top:
        print(f"  {w:<28} n={e['n']:>3} f={e['f']:.2f} (mediana {math.exp(e['med_log']):.2f}x)")
    return factors, before, after


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "run", "calibrate"])
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--n", type=int, default=4000)
    a = ap.parse_args()
    {"export": lambda: export(a.days, a.n), "run": run, "calibrate": calibrate}[a.cmd]()
