"""Regenera los datos de armas y el modelo caro/barato que baja la app (weapon_data.json).

Pedido de Fran (2026-11-02): que un arma nueva o un cambio de balance no obliguen a
sacar versión, y que corra con la PC apagada. Lo corre la Lambda riven-stock-weapon-data
una vez por día (cloud/estimator.yml); la app baja el resultado y, si no sirve, usa
los data/*.json que trae instalados.

Cada parte pasa una compuerta antes de publicarse; la que no pasa se reemplaza por
la publicada antes (o la del bundle si no hay):
  - armas: al menos WEAPON_DATA_MIN_WEAPONS y no menos del MIN_KEEP de las anteriores
    (un cambio de formato en WFCD no puede vaciar la lista);
  - modelo caro/barato: se entrena con las ventas viejas y se prueba con las nuevas
    (corte temporal); publica sólo si el AUC de la prueba llega a MIN_AUC. Lo aprobado
    se reentrena con todas las ventas.
Si ninguna parte pasa no se publica nada: el archivo viejo queda y el chequeo externo
(local-agent, linux/chequeo_estimador.py) avisa cuando pasa de un día.

Uso local (sin publicar): python tools/weapon_data_job.py
"""
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if HERE.name == "tools" else HERE   # en la Lambda todo queda en la raíz
sys.path[:0] = [str(ROOT), str(HERE)]

import pricing  # noqa: E402

SAMPLE = 80000     # ventas por corrida como mucho (las más nuevas)
HOLDOUT = 0.2      # las más nuevas, para probar
MIN_AUC = 0.8      # medido el 2026-11-02: 0.925 con el corte temporal (64 mil ventas); 0.5 es tirar una moneda
MIN_TEST = 1000    # con menos ventas de prueba el AUC no dice nada
MIN_KEEP = 0.9


def fetch_sales(client=None, limit=SAMPLE):
    """Las ventas limpias, las más nuevas primero. Va por el índice de _id (crece con el tiempo):
    el clúster gratis de Atlas no deja ordenar ni sortear ($sample) más de 32 MB en memoria."""
    import estimator_mongo
    db = estimator_mongo.db(client)
    q = {"suspect": {"$exists": False}, "price": {"$gte": 5}, "attrs.0": {"$exists": True}}
    proj = {"_id": 0, "weapon": 1, "price": 1, "attrs": 1, "rolls": 1, "rank": 1, "detected_at": 1}
    return list(db.sales.find(q, proj).sort("_id", -1).limit(limit))


def view(sale):
    return {"stats": [{"slug": a[0], "positive": bool(a[2])} for a in sale["attrs"]],
            "rolls": sale.get("rolls"), "rank": sale.get("rank")}


def auc(model, sales):
    """AUC de "se vendió a más de CUT_PRICE" con las ventas que el modelo sabe etiquetar.
    Devuelve (auc, ventas etiquetadas)."""
    from train_tier import CUT_PRICE
    pts = []
    for s in sales:
        t = pricing.tier(s["weapon"], view(s), model=model)
        if t:
            pts.append((t["p"], s["price"] > CUT_PRICE))
    pos = sum(y for _, y in pts)
    neg = len(pts) - pos
    if not pos or not neg:
        return None, len(pts)
    # Mann-Whitney con rangos promedio para los empates (p viene redondeado a 2 decimales).
    pts.sort(key=lambda t: t[0])
    rank_pos, i = 0.0, 0
    while i < len(pts):
        j = i
        while j < len(pts) and pts[j][0] == pts[i][0]:
            j += 1
        r = (i + j + 1) / 2
        rank_pos += r * sum(y for _, y in pts[i:j])
        i = j
    return (rank_pos - pos * (pos + 1) / 2) / (pos * neg), len(pts)


def holdout(sales):
    """Entrena con las viejas y mide con las nuevas: (auc, ventas de prueba etiquetadas)."""
    from train_tier import fit
    s = sorted(sales, key=lambda x: x["detected_at"])
    cut = int(len(s) * (1 - HOLDOUT))
    return auc(fit(s[:cut]), s[cut:])


def previous(url=pricing.WEAPON_DATA_URL):
    """(weapon_stats, tier_model) de lo publicado; si no hay o no valida, los del bundle."""
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            ok = pricing.check_weapon_data(json.load(r))
        if ok:
            return ok[0], ok[1], "publicado"
    except (OSError, ValueError):
        pass
    return pricing._bundle("weapon_stats.json"), pricing._bundle("tier_model.json"), "bundle"


def choose(new_stats, sales, prev_stats, prev_tier, now=None):
    """Arma el documento. Devuelve (doc, report); doc es None si no pasó ninguna parte."""
    report = {}
    need = max(pricing.WEAPON_DATA_MIN_WEAPONS, int(len(prev_stats) * MIN_KEEP))
    n = len(new_stats or {})
    stats_ok = n >= need and all(isinstance(v, dict) and isinstance(v.get("share"), dict)
                                 for v in (new_stats or {}).values())
    report["armas"] = {"ok": stats_ok, "n": n, "minimo": need, "antes": len(prev_stats),
                       "nuevas": sorted(set(new_stats or {}) - set(prev_stats))[:50]}
    score, n_test = holdout(sales) if len(sales) >= MIN_TEST / HOLDOUT else (None, 0)
    tier_ok = score is not None and n_test >= MIN_TEST and score >= MIN_AUC
    report["modelo"] = {"ok": tier_ok, "ventas": len(sales), "prueba": n_test,
                        "auc": None if score is None else round(score, 4), "minimo": MIN_AUC}
    if not (stats_ok or tier_ok):
        return None, report
    if tier_ok:
        from train_tier import fit
        model = fit(sales)
        report["modelo"]["n"] = model["n"]
    doc = {"schema": pricing.WEAPON_DATA_SCHEMA,
           "updated": (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "weapon_stats": new_stats if stats_ok else prev_stats,
           "tier_model": model if tier_ok else prev_tier, "report": report}
    if not pricing.check_weapon_data(doc):
        report["error"] = "el documento armado no valida"
        return None, report
    return doc, report


def run(client=None):
    import build_weapon_data
    prev_stats, prev_tier, origen = previous()
    try:
        new_stats = build_weapon_data.build()
    except Exception as e:  # noqa: BLE001 -- WFCD caído: sigue el modelo, las armas quedan
        print(f"WFCD: {e!r}")
        new_stats = None
    doc, report = choose(new_stats, fetch_sales(client), prev_stats, prev_tier)
    report["anterior"] = origen
    return doc, report


if __name__ == "__main__":
    doc, report = run()
    print(json.dumps(report, ensure_ascii=False, indent=1))
