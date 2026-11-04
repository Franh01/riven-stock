"""Entrena el modelo de precio con las ventas de Mongo y decide si se publica.

Corre en la Lambda riven-stock-price-model (handler_modelo) una vez por día; también se
puede correr a mano: `python tools/price_model_job.py --out modelo.json` (necesita
lightgbm, numpy, pymongo y MONGODB_URI o cloud/.env). A mano no publica nada.

Validación honesta: entrena con las ventas de [hoy-60 d, hoy-3 d) y mide con una muestra
al azar de las de los últimos 3 días, que el modelo no vio. Se publica exactamente ese
modelo (con los encodings de ese mismo entrenamiento) y solo si pasa la compuerta:
acierta (dentro de x1.5) al menos MIN_HIT de las ventas, le gana al estimado por
publicaciones en las ventas donde había mercado y no empeora las caras (100p o más).
"""
import collections
import datetime as dt
import json
import math
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import estimator_mongo as em   # noqa: E402
import price_model as pm       # noqa: E402
import pricing                 # noqa: E402

TRAIN_DAYS, TEST_DAYS = 60, 3
N_TEST, SEED = 3000, 1
MIN_TRAIN, MIN_TEST = 5000, 500
ROUNDS = 600
PARAMS = dict(objective="huber", alpha=0.6, learning_rate=0.05, num_leaves=63, min_child_samples=30,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, verbose=-1, seed=SEED,
              num_threads=2)
# Compuerta de publicación
MIN_HIT = 0.45          # fracción de ventas dentro de x1.5
MIN_GAIN = 0.02         # mejora mínima contra el estimado por publicaciones (donde lo hay)
MAX_LOSS_EXPENSIVE = 0.02
MAX_PURE_DIFF = 1e-4    # predicción en Python puro contra lightgbm, en log
# Corrección de sesgo por tramo de precio predicho
BIAS_EDGES = (30, 60, 120, 250, 500)
BIAS_MIN_N, BIAS_SHRINK, BIAS_MAX = 50, 100, 0.7
OK = math.log(1.5)
EXPENSIVE = 100
PROJ = {"weapon": 1, "attrs": 1, "rolls": 1, "rank": 1, "seller": 1, "price": 1, "detected_at": 1}


def _naive(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).replace(tzinfo=None)


def encode(train, rtypes):
    """Codificación del arma con las ventas de entrenamiento: mediana del log del precio
    (suavizada hacia la del tipo de riven), percentil 75 y cuántas ventas tiene."""
    import numpy as np
    by_w, by_t = collections.defaultdict(list), collections.defaultdict(list)
    for o in train:
        lp = math.log(o["price"])
        by_w[o["weapon"]].append(lp)
        if rtypes.get(o["weapon"]):
            by_t[rtypes[o["weapon"]]].append(lp)
    gmed = float(np.median([x for v in by_w.values() for x in v]))
    types = {k: round(float(np.median(v)), 6) for k, v in by_t.items()}
    weapons = {}
    for w, v in by_w.items():
        n = len(v)
        wenc = round((n * float(np.median(v)) + 5 * types.get(rtypes.get(w), gmed)) / (n + 5), 6)
        q75 = round(float(np.percentile(v, 75)), 6) if n >= 5 else wenc
        weapons[w] = [wenc, q75, round(math.log1p(n), 6)]
    return {"gmed": round(gmed, 6), "types": types, "weapons": weapons}


def feats(o, rtypes, enc):
    return pm.features(o["weapon"], rtypes.get(o["weapon"]), [tuple(a) for a in o["attrs"]],
                       o.get("rolls"), o.get("rank"), enc)


def matrix(dicts, cols):
    import numpy as np
    ix = {c: i for i, c in enumerate(cols)}
    X = np.zeros((len(dicts), len(cols)))
    for i, d in enumerate(dicts):
        for k, v in d.items():
            j = ix.get(k)
            if j is not None:
                X[i, j] = v
    return X


def _bucket(y):
    for i, edge in enumerate(BIAS_EDGES):
        if y <= math.log(edge):
            return i
    return len(BIAS_EDGES)


def fit_bias(preds, ys):
    """[[techo_log, corrección], ...]: mediana del residuo por tramo, achicada según cuántas
    ventas tiene el tramo (los tramos con menos de BIAS_MIN_N no se corrigen)."""
    res = collections.defaultdict(list)
    for p, y in zip(preds, ys):
        res[_bucket(p)].append(y - p)
    out = []
    for i in range(len(BIAS_EDGES) + 1):
        r = res.get(i, [])
        corr = 0.0
        if len(r) >= BIAS_MIN_N:
            corr = statistics.median(r) * len(r) / (len(r) + BIAS_SHRINK)
            corr = max(-BIAS_MAX, min(BIAS_MAX, corr))
        out.append([round(math.log(BIAS_EDGES[i]), 6) if i < len(BIAS_EDGES) else None, round(corr, 6)])
    return out if any(c for _, c in out) else []


def hit(errs):
    return sum(abs(e) <= OK for e in errs) / len(errs) if errs else None


def _median_ratio(errs):
    return round(math.exp(statistics.median(errs)), 4) if errs else None


def run(client=None, now=None, seed=SEED):
    """Devuelve (documento a publicar o None, reporte)."""
    import lightgbm as lgb
    import numpy as np

    now = now or dt.datetime.now(dt.timezone.utc).timestamp()
    t_test, t_train = now - TEST_DAYS * 86400, now - TRAIN_DAYS * 86400
    database = em.db(client)
    train = list(database.sales.find({**em.SALES_Q, "detected_at": {"$gte": _naive(t_train), "$lt": _naive(t_test)}},
                                     PROJ))
    test = list(database.sales.find({**em.SALES_Q, "detected_at": {"$gte": _naive(t_test)}}, PROJ))
    rnd = random.Random(seed)
    test = rnd.sample(test, min(N_TEST, len(test)))   # al azar: nunca las más nuevas
    rep = {"train": len(train), "test": len(test)}
    if len(train) < MIN_TRAIN or len(test) < MIN_TEST:
        return None, {**rep, "motivo": "pocas ventas"}
    rtypes = em.fetch_rtypes() or em.stored_rtypes(database[em.COL])
    listings = em.listings_for(database, sorted({o["weapon"] for o in test}), _naive(t_test - 86400))

    enc = encode(train, rtypes)
    ftr = [feats(o, rtypes, enc) for o in train]
    cols = sorted({k for d in ftr for k in d})
    booster = lgb.train(PARAMS, lgb.Dataset(matrix(ftr, cols), np.log([o["price"] for o in train])),
                        num_boost_round=ROUNDS)
    del ftr

    fte = [feats(o, rtypes, enc) for o in test]
    lgb_pred = booster.predict(matrix(fte, cols))
    trees = pm.export_trees(booster.dump_model())
    doc = {"schema": pm.SCHEMA, "features_version": pm.FEATURES_VERSION,
           "updated": dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "features": cols, "trees": trees, "enc": enc, "bias": []}
    model = pm.check(json.loads(json.dumps(doc)))   # lo mismo que va a leer la app
    if model is None:
        return None, {**rep, "motivo": "el modelo exportado no valida"}
    pure = [pm.predict_log(model, d) for d in fte]
    rep["pure_diff"] = max(abs(a - b) for a, b in zip(pure, lgb_pred))

    ys = [math.log(o["price"]) for o in test]
    # Corrección por tramo, validada en mitades cruzadas: cada mitad se corrige con lo que
    # se ajustó en la otra. Solo se usa si no empeora.
    idx = list(range(len(test)))
    rnd.shuffle(idx)
    halves = (idx[: len(idx) // 2], idx[len(idx) // 2:])
    crossed = list(pure)
    for a, b in (halves, halves[::-1]):
        bias = fit_bias([pure[i] for i in a], [ys[i] for i in a])
        for i in b:
            crossed[i] = pure[i] + pm.bias_for(bias, pure[i])
    exp_ix = [i for i, o in enumerate(test) if o["price"] >= EXPENSIVE]
    e_raw = [p - y for p, y in zip(pure, ys)]
    e_crs = [p - y for p, y in zip(crossed, ys)]
    use_bias = (hit(e_crs) >= hit(e_raw)
                and (not exp_ix or hit([e_crs[i] for i in exp_ix]) >= hit([e_raw[i] for i in exp_ix])))
    if use_bias:
        doc["bias"] = fit_bias(pure, ys)
    errs = e_crs if use_bias else e_raw

    # El estimado de hoy (por publicaciones) donde se puede reconstruir el mercado.
    with_mkt = []
    for i, o in enumerate(test):
        t = em._ts(o["detected_at"])
        market = em.market_at(listings, o["weapon"], t, o.get("seller"))
        if not market:
            continue
        view = {"stats": [{"slug": a, "value": v, "positive": p} for a, v, p in o["attrs"]],
                "rolls": o.get("rolls") or 0, "rank": o.get("rank")}
        est = pricing.estimate(view, market, rtype=rtypes.get(o["weapon"]), weapon=o["weapon"], model=False)
        if est and est.get("price"):
            with_mkt.append((i, math.log(est["price"]) - ys[i]))
    m_ix = [i for i, _ in with_mkt]
    me_ix = [i for i in m_ix if test[i]["price"] >= EXPENSIVE]
    cur = dict(with_mkt)
    rep.update({
        "features": len(cols), "bias": bool(doc["bias"]),
        "hit": round(hit(errs), 4), "ratio": _median_ratio(errs),
        "hit_caras": round(hit([errs[i] for i in exp_ix]), 4) if exp_ix else None,
        "con_mercado": len(m_ix), "caras_con_mercado": len(me_ix),
        "modelo_mercado": round(hit([errs[i] for i in m_ix]), 4) if m_ix else None,
        "actual_mercado": round(hit([cur[i] for i in m_ix]), 4) if m_ix else None,
        "modelo_caras": round(hit([errs[i] for i in me_ix]), 4) if me_ix else None,
        "actual_caras": round(hit([cur[i] for i in me_ix]), 4) if me_ix else None,
        "ratio_actual": _median_ratio([cur[i] for i in m_ix]),
    })
    fails = []
    if rep["pure_diff"] > MAX_PURE_DIFF:
        fails.append("la predicción en Python puro no coincide con lightgbm")
    if rep["hit"] < MIN_HIT:
        fails.append("acierta poco")
    if len(m_ix) < MIN_TEST or rep["modelo_mercado"] - rep["actual_mercado"] < MIN_GAIN:
        fails.append("no le gana al estimado por publicaciones")
    if me_ix and rep["modelo_caras"] < rep["actual_caras"] - MAX_LOSS_EXPENSIVE:
        fails.append("empeora las caras")
    rep["motivo"] = "; ".join(fails) or None
    rep["publicable"] = not fails
    doc["report"] = {k: rep[k] for k in ("train", "test", "hit", "modelo_mercado", "actual_mercado",
                                         "modelo_caras", "actual_caras", "bias")}
    return (None if fails else doc), rep


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="dónde dejar price_model.json si pasa la compuerta")
    args = ap.parse_args()
    print("PROGRESS 0/1", flush=True)
    client = em.db_client()
    try:
        doc, rep = run(client)
    finally:
        client.close()
    print(json.dumps(rep, ensure_ascii=False), flush=True)
    if doc and args.out:
        Path(args.out).write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
        print(args.out, Path(args.out).stat().st_size // 1024, "KB")
    print("PROGRESS 1/1", flush=True)


if __name__ == "__main__":
    main()
