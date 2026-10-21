"""Alertas de oportunidad: publicaciones muy por debajo de lo que valen según sus comparables."""

from pricing import estimate

MAX_PER_WEAPON = 3      # avisos por arma y pasada (las mejores)
CHEAP_FRACTION = 0.3    # solo se evalúan las más baratas del mercado: las caras no pueden ser oportunidad


def find(market, rtype, threshold, min_gain, skip_ids=()):
    """market: publicaciones slim de un arma. threshold: % por debajo del estimado (p. ej. 30).
    Devuelve las oportunidades, la de mayor ganancia primero."""
    live = sorted((o for o in market if o.get("p") and o["id"] not in skip_ids), key=lambda o: o["p"])
    cheap = [o for o in live if o["st"] in ("ingame", "online")][:max(5, int(len(live) * CHEAP_FRACTION))]
    out = []
    for o in cheap:
        view = {"stats": [{"slug": s, "value": v, "positive": p} for s, v, p in o["s"]],
                "rolls": o.get("r") or 0, "rank": o.get("k")}
        est = estimate(view, market, exclude_id=o["id"], rtype=rtype)
        if not est or est["confidence"] == "baja" or est["n"] < 3:
            continue
        gain = est["price"] - o["p"]
        if gain >= min_gain and o["p"] <= est["price"] * (1 - threshold / 100):
            out.append({"id": o["id"], "price": o["p"], "estimate": est["price"], "gain": gain,
                        "confidence": est["confidence"], "name": o.get("n", ""), "seller": o.get("nm"),
                        "rolls": o.get("r") or 0})
    out.sort(key=lambda x: -x["gain"])
    return out[:MAX_PER_WEAPON]
