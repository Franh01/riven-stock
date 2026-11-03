"""Comparar el stock publicado contra el mercado: caro, barato o estancado según el estimado."""

from pricing import estimate

BAND = 0.25      # % por encima/debajo del estimado para marcar caro o barato
MIN_DIFF = 15    # y al menos esta diferencia en platinum


def stale(hours, need_hours):
    """Estancado: lleva need_hours online al mismo precio sin venderse. No depende del estimado."""
    return hours is not None and bool(need_hours) and hours >= need_hours


def stale_only(view, hours):
    """Resultado de un riven estancado sin estimado confiable (o sin mercado en el caché)."""
    return {"price": view["price"], "estimate": None, "low": None, "high": None, "diff": None,
            "pct": None, "confidence": None, "hours": hours, "tags": ["estancado"]}


def position(view, market, rtype, hours, need_hours, weapon=None):
    """view: contrato propio (auction_view). market: publicaciones slim del arma (caché).
    hours: horas online al precio actual. Sin estimado confiable devuelve solo "estancado"
    si corresponde, o None; si no, estimado, desvío y etiquetas."""
    est = estimate(view, market, exclude_id=view["id"], rtype=rtype, weapon=weapon)
    if not est or est["confidence"] == "baja" or est["n"] < 3:
        return stale_only(view, hours) if stale(hours, need_hours) else None
    price, ref = view["price"], est["price"]
    diff = price - ref
    tags = []
    if diff >= MIN_DIFF and price >= ref * (1 + BAND):
        tags.append("caro")
    elif -diff >= MIN_DIFF and price <= ref * (1 - BAND):
        tags.append("barato")
    if stale(hours, need_hours):
        tags.append("estancado")
    return {"price": price, "estimate": ref, "low": est["low"], "high": est["high"], "diff": diff,
            "pct": round(diff / ref * 100) if ref else 0, "confidence": est["confidence"],
            "hours": hours, "tags": tags}
