"""Comparar el stock publicado contra el mercado: caro, barato o estancado según el estimado."""

from pricing import estimate

BAND = 0.25      # % por encima/debajo del estimado para marcar caro o barato
MIN_DIFF = 15    # y al menos esta diferencia en platinum


def position(view, market, rtype, hours, need_hours, weapon=None):
    """view: contrato propio (auction_view). market: publicaciones slim del arma (caché).
    Devuelve None si no hay estimado confiable; si no, estimado, desvío y etiquetas."""
    est = estimate(view, market, exclude_id=view["id"], rtype=rtype, weapon=weapon)
    if not est or est["confidence"] == "baja" or est["n"] < 3:
        return None
    price, ref = view["price"], est["price"]
    diff = price - ref
    tags = []
    if diff >= MIN_DIFF and price >= ref * (1 + BAND):
        tags.append("caro")
    elif -diff >= MIN_DIFF and price <= ref * (1 - BAND):
        tags.append("barato")
    if hours is not None and need_hours and hours >= need_hours:
        tags.append("estancado")
    return {"estimate": ref, "low": est["low"], "high": est["high"], "diff": diff,
            "pct": round(diff / ref * 100) if ref else 0, "confidence": est["confidence"],
            "tags": tags}
