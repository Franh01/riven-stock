"""Entrena la etiqueta caro/barato (data/tier_model.json) con las ventas limpias exportadas a JSON.

Uso: python tools/train_tier.py ventas.json   (cada venta: weapon, price, attrs [[slug, valor, positivo]], rolls, rank)
Regresión logística de "se vendió a más de 80p" sobre el precio base del arma y los stats. Requiere numpy.
"""
import collections
import json
import sys
from pathlib import Path

import numpy as np

CUT_PRICE, MIN_WEAPON, MIN_STAT = 80, 8, 30


def main(path):
    S = [s for s in json.load(open(path, encoding="utf-8")) if s.get("price", 0) >= 5 and s.get("attrs")]
    cnt = collections.Counter(s["weapon"] for s in S)
    S = [s for s in S if cnt[s["weapon"]] >= MIN_WEAPON]
    S.sort(key=lambda s: s["detected_at"])
    cols = sorted({("+" if a[2] else "-") + a[0] for s in S for a in s["attrs"]}) + ["rolls", "rank10", "npos3"]
    ix = {c: i for i, c in enumerate(cols)}
    X = np.zeros((len(S), len(cols)))
    for i, s in enumerate(S):
        n = 0
        for slug, _, pos in s["attrs"]:
            X[i, ix[("+" if pos else "-") + slug]] = 1
            n += pos
        X[i, ix["rolls"]] = np.log1p(s.get("rolls") or 0)
        X[i, ix["rank10"]] = (s.get("rank") or 0) >= 8
        X[i, ix["npos3"]] = n == 3
    y = np.log([s["price"] for s in S])
    t = (np.exp(y) > CUT_PRICE).astype(float)
    W = [s["weapon"] for s in S]
    gm = float(np.median(y))
    by = collections.defaultdict(list)
    for w, v in zip(W, y):
        by[w].append(v)
    base_w = {w: round(float(np.median(v)), 3) for w, v in by.items() if len(v) >= 3}
    base = np.array([base_w.get(w, gm) for w in W])
    A = np.column_stack([np.ones(len(S)), base, X])
    keep = np.array([True, True] + [X[:, j].sum() >= MIN_STAT for j in range(len(cols))])
    A = A[:, keep]
    b = np.zeros(A.shape[1])
    for _ in range(30):
        p = 1 / (1 + np.exp(-A @ b))
        b -= np.linalg.solve((A * (p * (1 - p))[:, None]).T @ A + 5 * np.eye(len(b)), A.T @ (p - t) + 5 * b)
    p = 1 / (1 + np.exp(-A @ b))
    kc = [c for c, k in zip(["icpt", "base"] + cols, keep) if k]
    out = {"coef": {c: round(float(v), 4) for c, v in zip(kc, b)}, "base": base_w, "gm": round(gm, 3),
           "hi": round(float(np.quantile(p, 0.8)), 3), "lo": round(float(np.quantile(p, 0.2)), 3), "n": len(S)}
    Path(__file__).parent.parent.joinpath("data", "tier_model.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(len(S), "ventas;", len(kc), "coeficientes; umbrales", out["lo"], out["hi"])


if __name__ == "__main__":
    main(sys.argv[1])
