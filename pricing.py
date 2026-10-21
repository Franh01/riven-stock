"""Precio estimado de un riven según publicaciones comparables del mismo arma.

No usa las más baratas (suelen ser los peores rolls): pondera cada publicación por qué tan
parecida es (stats positivos compartidos, valores, negativo, rerolls) y toma la mediana ponderada.
"""

# Stats que el mercado paga más; el resto pesa 1.
WEIGHTS = {
    "critical_chance": 3, "critical_damage": 3, "multishot": 3, "base_damage_/_melee_damage": 2.5,
    "damage_vs_grineer": 0.5, "damage_vs_corpus": 0.5, "damage_vs_infested": 0.5,
    "fire_rate_/_attack_speed": 1.5, "speed": 1.5, "status_chance": 1.5, "status_duration": 1,
    "reload_speed": 0.7, "magazine_capacity": 0.5, "ammo_maximum": 0.4, "zoom": 0.2,
    "recoil": 0.3, "weapon_recoil": 0.3, "punch_through": 0.4, "projectile_speed": 0.5,
    "range": 0.5, "combo_duration": 0.7, "initial_combo": 0.7, "chance_to_gain_extra_combo_count": 0.5,
    "finisher_damage": 0.5, "slide_attack_critical_chance": 0.4, "channeling_damage": 0.4,
    "channeling_efficiency": 0.4, "chance_to_gain_combo_count": 0.5,
}
MIN_SIM = 0.35      # por debajo no se considera comparable
MAX_COMPS = 12      # cuántos comparables entran al cálculo


def _w(slug):
    return WEIGHTS.get(slug, 1.0)


def _split(stats):
    pos = {s["slug"]: s["value"] for s in stats if s["positive"]}
    neg = [s["slug"] for s in stats if not s["positive"]]
    return pos, (neg[0] if neg else None)


def slim(a):
    """Contrato crudo de warframe.market -> lo mínimo para comparar (va al caché)."""
    item = a["item"]
    return {
        "id": a["id"], "p": a["buyout_price"], "st": a["owner"].get("status"),
        "s": [[x["url_name"], x["value"], bool(x["positive"])] for x in item["attributes"]],
        "r": item.get("re_rolls") or 0,
    }


def similarity(pos, neg, rolls, other):
    opos = {s: v for s, v, p in other["s"] if p}
    oneg = next((s for s, v, p in other["s"] if not p), None)
    union = set(pos) | set(opos)
    if not union:
        return 0.0
    shared = set(pos) & set(opos)
    got = 0.0
    for s in shared:
        a, b = abs(pos[s]), abs(opos[s])
        close = min(a, b) / max(a, b) if max(a, b) else 1.0
        got += _w(s) * (0.6 + 0.4 * close)
    sim = got / sum(_w(s) for s in union)
    if neg != oneg:
        # sin negativo vale más que con uno; un negativo distinto cambia poco
        sim *= 0.9 if (neg and oneg) else 0.8
    sim *= 1.0 - min(abs(rolls - other["r"]), 20) * 0.004
    return max(sim, 0.0)


def _wquantile(pairs, q):
    """pairs: [(valor, peso)]; cuantil ponderado."""
    pairs = sorted(pairs)
    total = sum(w for _, w in pairs)
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= q * total:
            return v
    return pairs[-1][0]


def estimate(view, market, exclude_id=None):
    """view: auction_view de mi riven. Devuelve {price, low, high, n, confidence, comps} o None."""
    pos, neg = _split(view["stats"])
    if not pos or not market:
        return None
    scored = []
    for o in market:
        if o["id"] == exclude_id or not o["p"]:
            continue
        sim = similarity(pos, neg, view.get("rolls") or 0, o)
        if sim >= MIN_SIM:
            scored.append((sim, o))
    if not scored:
        return None
    scored.sort(key=lambda t: -t[0])
    top = scored[:MAX_COMPS]
    pairs = [(o["p"], (sim ** 3) * (1.0 if o["st"] in ("ingame", "online") else 0.5)) for sim, o in top]
    avg_sim = sum(s for s, _ in top) / len(top)
    conf = "alta" if len(top) >= 6 and avg_sim >= 0.7 else "media" if len(top) >= 3 and avg_sim >= 0.5 else "baja"
    return {
        "price": round(_wquantile(pairs, 0.5)),
        "low": round(_wquantile(pairs, 0.25)),
        "high": round(_wquantile(pairs, 0.75)),
        "n": len(top), "confidence": conf, "avg_sim": round(avg_sim, 2),
        "comps": [{"price": o["p"], "sim": round(s, 2), "status": o["st"], "rolls": o["r"],
                   "stats": [{"slug": x, "value": v, "positive": p} for x, v, p in o["s"]]}
                  for s, o in top],
    }
