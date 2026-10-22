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
# Ajustes por tipo de arma (rivenType de warframe.market): lo que cambia respecto de WEIGHTS.
TYPE_WEIGHTS = {
    "rifle": {"multishot": 3.5, "base_damage_/_melee_damage": 3, "fire_rate_/_attack_speed": 2,
              "slash_damage": 1.2, "toxin_damage": 1.5, "heat_damage": 1.5, "cold_damage": 1.5,
              "electric_damage": 1.5},
    "shotgun": {"critical_chance": 3.5, "critical_damage": 3, "status_chance": 2.5, "slash_damage": 2,
                "multishot": 2, "toxin_damage": 1.8, "fire_rate_/_attack_speed": 1.5},
    "pistol": {"multishot": 3.5, "critical_chance": 3, "fire_rate_/_attack_speed": 2,
               "toxin_damage": 1.5, "status_chance": 1.5},
    "melee": {"critical_chance": 3.5, "critical_damage": 3, "fire_rate_/_attack_speed": 2.5,
              "slash_damage": 2, "range": 1, "combo_duration": 1, "initial_combo": 1.2,
              "chance_to_gain_extra_combo_count": 1, "finisher_damage": 0.8, "base_damage_/_melee_damage": 2.5},
    "kitgun": {"critical_chance": 3, "multishot": 3, "fire_rate_/_attack_speed": 2},
    "zaw": {"critical_chance": 3, "fire_rate_/_attack_speed": 2.5, "initial_combo": 1.2, "range": 1},
}
MIN_SIM = 0.35      # por debajo no se considera comparable
MAX_COMPS = 12      # cuántos comparables entran al cálculo


def _w(slug, rtype=None):
    over = TYPE_WEIGHTS.get(rtype)
    if over and slug in over:
        return over[slug]
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
        "n": item.get("name", ""), "m": item.get("mastery_level"), "c": a.get("created"), "ls": a["owner"].get("last_seen"), "nm": a["owner"].get("ingame_name"),
        "k": item.get("mod_rank"),   # rango del mod (8 = maxeado); None en datos viejos del caché
    }


def _max_rank_factor(rank):
    """Los valores que muestra la API dependen del rango: pasarlos a su equivalente maxeado."""
    return 9 / (rank + 1) if rank is not None and 0 <= rank <= 8 else 1.0


# Multiplicador de los valores positivos según la configuración (positivos, con negativo): wiki de Warframe.
CONFIG_BONUS = {(2, False): 0.99, (2, True): 1.2375, (3, False): 0.75, (3, True): 0.9375}


def _config_bonus(npos, has_neg):
    return CONFIG_BONUS.get((npos, bool(has_neg)), 1.0)


def similarity(pos, neg, rolls, other, rtype=None, rank=None):
    f_mine = _max_rank_factor(rank)
    f_other = _max_rank_factor(other.get("k")) if rank is not None else 1.0
    oraw = [(s, v) for s, v, p in other["s"] if p]
    oneg = next((s for s, v, p in other["s"] if not p), None)
    # el mismo valor vale distinto según la configuración: se lleva a su equivalente sin multiplicador
    f_mine /= _config_bonus(len(pos), neg)
    f_other /= _config_bonus(len(oraw), oneg)
    pos = {s: v * f_mine for s, v in pos.items()}
    opos = {s: v * f_other for s, v in oraw}
    union = set(pos) | set(opos)
    if not union:
        return 0.0
    shared = set(pos) & set(opos)
    got = 0.0
    for s in shared:
        a, b = abs(pos[s]), abs(opos[s])
        close = min(a, b) / max(a, b) if max(a, b) else 1.0
        got += _w(s, rtype) * (0.3 + 0.7 * close ** 1.5)   # los valores pesan: un roll flojo no vale lo mismo
    # cubrir MIS stats pesa mas que que el otro tenga extras
    mine = sum(_w(s, rtype) for s in pos)
    sim = (got / sum(_w(s, rtype) for s in union)) ** 0.4 * (got / mine) ** 0.6
    if neg != oneg:
        # sin negativo vale más que con uno; un negativo distinto cambia poco
        sim *= 0.9 if (neg and oneg) else 0.8
    if len(pos) != len(opos):
        sim *= 0.92   # 2 y 3 positivos no se venden igual
    sim *= 1.0 - min(abs(rolls - other["r"]), 20) * 0.004
    return max(sim, 0.0)


def _age_days(iso):
    """Días desde una fecha ISO de warframe.market; None si no se puede leer."""
    try:
        t = _dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=_dt.timezone.utc)
        return max(0.0, (_dt.datetime.now(_dt.timezone.utc) - t).total_seconds() / 86400)
    except (ValueError, TypeError):
        return None


def _stale(o):
    """Una publicación vieja que no se vendió es mala referencia de precio."""
    d = _age_days(o.get("c")) if o.get("c") else None
    return 1.0 if d is None or d < 14 else 0.7 if d < 30 else 0.5


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


def estimate(view, market, exclude_id=None, rtype=None, weapon=None):
    """view: auction_view de mi riven. Devuelve {price, low, high, n, confidence, comps} o None."""
    pos, neg = _split(view["stats"])
    if not pos or not market:
        return None
    scored = []
    for o in market:
        if o["id"] == exclude_id or not o["p"]:
            continue
        sim = similarity(pos, neg, view.get("rolls") or 0, o, rtype, view.get("rank"))
        if sim >= MIN_SIM:
            scored.append((sim, o))
    if not scored:
        return None
    scored.sort(key=lambda t: -t[0])
    top = scored[:MAX_COMPS]
    pairs = [(o["p"], (sim ** 5) * (1.0 if o["st"] in ("ingame", "online") else 0.5) * _stale(o)) for sim, o in top]
    avg_sim = sum(s for s, _ in top) / len(top)
    conf = "alta" if len(top) >= 6 and avg_sim >= 0.7 else "media" if len(top) >= 3 and avg_sim >= 0.5 else "baja"
    adj, reasons = weapon_adjust(weapon, view["stats"]) if weapon else (1.0, [])
    price, low, high = (round(_wquantile(pairs, q) * adj) for q in (0.5, 0.25, 0.75))
    # Techo 1: lo que ya lleva publicado sin venderse a mi precio
    days = _age_days(view.get("created")) if view.get("created") and view.get("price") else None
    if days is not None and days >= 3:
        cap = round(view["price"] * max(1.3, 3.0 - days / 7))
        if price > cap:
            price, low, high = cap, min(low, cap), min(high, cap)
            reasons.append({"key": "listedLong", "d": int(days), "p": view["price"]})
    # Techo 2: si los comparables más parecidos están todos mucho más baratos
    close = sorted(o["p"] for s, o in top if s >= 0.6)
    if len(close) >= 3:
        cap = round(close[len(close) // 2] * 2.5)
        if price > cap:
            price, low, high = cap, min(low, cap), min(high, cap)
            reasons.append({"key": "cheaperCap", "n": len(close)})
    if any(_stale(o) < 1 for _, o in top):
        reasons.append({"key": "staleComps"})
    return {
        "adj": round(adj, 2), "reasons": reasons,
        "price": price, "low": low, "high": high,
        "n": len(top), "confidence": conf, "avg_sim": round(avg_sim, 2),
        "comps": [{"id": o["id"], "price": o["p"], "sim": round(s, 2), "status": o["st"], "rolls": o["r"], "rank": o.get("k"),
                   "created": o.get("c"), "last_seen": o.get("ls"), "seller": o.get("nm"),
                   "stats": [{"slug": x, "value": v, "positive": p} for x, v, p in o["s"]]}
                  for s, o in top],
    }


import datetime as _dt
import json as _json
from pathlib import Path as _Path

_WSTATS = None
PHYS_STAT = {"impact_damage": "impact", "puncture_damage": "puncture", "slash_damage": "slash"}


def weapon_stats(weapon):
    """Datos del arma (reparto de daño, crítico, estado) de data/weapon_stats.json; None si no está."""
    global _WSTATS
    if _WSTATS is None:
        try:
            _WSTATS = _json.loads((_Path(__file__).parent / "data" / "weapon_stats.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _WSTATS = {}
    return _WSTATS.get(weapon)


def weapon_adjust(weapon, stats):
    """Ajuste por lo que el arma realmente usa. Devuelve (factor, motivos[{key, slug, ...}])."""
    w = weapon_stats(weapon)
    if not w:
        return 1.0, []
    share = w.get("share") or {}
    factor, reasons = 1.0, []
    for st in stats:
        kind = PHYS_STAT.get(st["slug"])
        if not kind:
            continue
        sh = share.get(kind, 0.0)
        if not st["positive"]:
            if sh >= 0.4:      # negativo sobre el daño principal: muy malo, escala con el valor
                f = max(0.25, 1 - min(abs(st["value"]), 100) / 100 * 0.75 * min(1, sh / 0.6))
                factor *= f
                reasons.append({"key": "negMain", "slug": st["slug"], "share": round(sh * 100), "f": round(f, 2)})
            elif sh <= 0.15:   # negativo sobre un daño que el arma casi no usa: casi gratis
                factor *= 1.1
                reasons.append({"key": "negUnused", "slug": st["slug"], "share": round(sh * 100), "f": 1.1})
        elif sh <= 0.15:       # positivo sobre un daño que el arma casi no usa: vale poco
            factor *= 0.85
            reasons.append({"key": "posUnused", "slug": st["slug"], "share": round(sh * 100), "f": 0.85})
        elif sh >= 0.5:
            reasons.append({"key": "posMain", "slug": st["slug"], "share": round(sh * 100), "f": 1.0})
    return factor, reasons
