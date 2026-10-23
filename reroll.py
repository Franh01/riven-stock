"""¿Conviene gastar Kuva en rolear un riven que ya tengo? Simula rivens al azar y los valora con el estimador.

Reglas del juego usadas: tras cada tirada se puede quedarse con el riven anterior o con el nuevo, así que
con n tiradas queda max(actual, mejor de las n). El Kuva de cada tirada sube hasta un tope.
El resultado es orientativo: el estimador valora con precios publicados, no con ventas reales.
"""

import random

from pricing import estimate

KUVA_COSTS = [900, 1000, 1200, 1400, 1700, 2000, 2350, 2750, 3150, 3500]   # la tirada nº i (desde 0) cuesta KUVA_COSTS[min(i, 9)]
MAX_TRIES = 6             # hasta cuántas tiradas seguidas se evalúan
SAMPLES = 400             # rivens al azar por evaluación
SCALE = 9000              # valor = base de DE x SCALE x disposición x multiplicador x tirada (medido contra el mercado)
ROLL_LOW, ROLL_HIGH = 0.9, 1.1
# (positivos, tiene negativo) -> multiplicador de los positivos; el del negativo según cuántos positivos hay
POS_MULT = {(2, False): 0.99, (2, True): 1.2375, (3, False): 0.75, (3, True): 0.9375}
NEG_MULT = {2: 0.47, 3: 0.70}
KUVA_PLAT = 10            # exigencia interna: platinum de ganancia por cada 1000 Kuva
MIN_GAIN = 15             # ganancia neta mínima (platinum) para recomendar rolear
MIN_MARKET = 8            # publicaciones mínimas del arma para opinar
MAX_NO_REF = 0.8          # si más de esta fracción de rivens simulados no tiene comparables, no hay datos


def kuva_cost(rolls_done, tries):
    """Kuva total de `tries` tiradas más, habiendo hecho ya `rolls_done`."""
    return sum(KUVA_COSTS[min(rolls_done + i, len(KUVA_COSTS) - 1)] for i in range(tries))


def _pools(rtype, attrs, bases):
    """Stats posibles de un tipo de arma: (para positivos, para negativos)."""
    pos, neg = [], []
    for a in attrs:
        slug = a["slug"]
        if slug not in bases or (a.get("exclusiveTo") and rtype not in a["exclusiveTo"]):
            continue
        if not a.get("negativeOnly"):
            pos.append(slug)
        if not a.get("positiveOnly"):
            neg.append(slug)
    return pos, neg


def _random_riven(rng, pos_pool, neg_pool, bases, disposition):
    npos = 2 if rng.random() < 0.5 else 3
    has_neg = rng.random() < 0.5
    picked = rng.sample(pos_pool, npos)
    mult = POS_MULT[(npos, has_neg)]
    stats = [{"slug": s, "value": round(bases[s] * SCALE * disposition * mult * rng.uniform(ROLL_LOW, ROLL_HIGH), 1),
              "positive": True} for s in picked]
    if has_neg:
        choices = [s for s in neg_pool if s not in picked]
        if choices:
            s = rng.choice(choices)
            stats.append({"slug": s, "value": -round(bases[s] * SCALE * disposition * NEG_MULT[npos] * rng.uniform(ROLL_LOW, ROLL_HIGH), 1),
                          "positive": False})
    return stats


def _percentile(sorted_vals, q):
    return sorted_vals[min(len(sorted_vals) - 1, int(q * len(sorted_vals)))]


def _good_stats(market):
    """Stats positivos que aparecen mucho más en las publicaciones caras que en el resto: {slug: veces en caras}."""
    priced = sorted((o for o in market if o.get("p")), key=lambda o: o["p"])
    if len(priced) < MIN_MARKET:
        return {}
    cut = len(priced) * 3 // 4
    rich, rest = priced[cut:], priced[:cut]
    def freq(group):
        c = {}
        for o in group:
            for s in o["s"]:
                if s[2]:
                    c[s[0]] = c.get(s[0], 0) + 1
        return c
    fr, fo = freq(rich), freq(rest)
    return {s: n for s, n in fr.items() if n >= 3 and n / len(rich) >= 1.5 * (fo.get(s, 0) / max(1, len(rest)))}


def _example(market, good, mine_slugs):
    """Una publicación cara del arma con stats buenos que mi riven no tiene (la de precio mediano entre las mejores, para no mostrar un outlier)."""
    cands = []
    for o in market:
        if not o.get("p"):
            continue
        hits = [s[0] for s in o["s"] if s[2] and s[0] in good and s[0] not in mine_slugs]
        if hits:
            cands.append((len(hits), o["p"], o))
    if not cands:
        return None, []
    top = sorted(cands, key=lambda c: (-c[0], -c[1]))[:7]
    top.sort(key=lambda c: c[1])
    o = top[len(top) // 2][2]
    return {"name": o.get("n"), "price": o["p"], "rolls": o.get("r", 0),
            "stats": [{"slug": s[0], "value": s[1], "positive": s[2]} for s in o["s"]]}, [s[0] for s in o["s"] if s[2] and s[0] in good]


def evaluate(view, market, rtype, weapon, disposition, attrs, bases, kuva_plat):
    """view: auction_view de mi riven. market: publicaciones slim del arma. attrs: catálogo de stats de
    warframe.market. bases: riven_bases.json[rtype]. kuva_plat: platinum que vale 1000 Kuva.
    Devuelve el consejo o None si no se puede opinar."""
    if not market or len(market) < MIN_MARKET or not rtype or not disposition or not bases:
        return None
    pos_pool, neg_pool = _pools(rtype, attrs, bases)
    if len(pos_pool) < 3:
        return None
    # mi riven valorado igual que los simulados: sin precio ni antigüedad propios, para que sea comparable
    mine = dict(view, price=None, created=None)
    cur = estimate(mine, market, exclude_id=view.get("id"), rtype=rtype, weapon=weapon)
    if not cur or cur["confidence"] == "baja" or cur["n"] < 3:
        return None
    current = cur["price"]
    prices = sorted(o["p"] for o in market if o.get("p"))
    floor = _percentile(prices, 0.1)           # un riven sin comparables se asume de lo más barato
    rolls = (view.get("rolls") or 0)
    rng = random.Random(f"{weapon}:{rolls}:{len(market)}")
    vals, no_ref = [], 0
    for _ in range(SAMPLES):
        stats = _random_riven(rng, pos_pool, neg_pool, bases, disposition)
        e = estimate({"stats": stats, "rolls": rolls + 3, "rank": 8}, market, rtype=rtype, weapon=weapon)
        if e and e["n"] >= 2:
            vals.append(e["price"])
        else:
            vals.append(floor)
            no_ref += 1
    if no_ref / SAMPLES > MAX_NO_REF:
        return None
    vals.sort()
    n = len(vals)
    ys = [max(v, current) for v in vals]       # me quedo con el mejor de los dos
    kuva_value = kuva_plat / 1000.0
    best_net, best_n, curve = 0.0, 0, []
    for k in range(1, MAX_TRIES + 1):
        # esperanza del máximo de k tiradas: sum Y_i * ((i/N)^k - ((i-1)/N)^k)
        exp_max = sum(y * (((i + 1) / n) ** k - (i / n) ** k) for i, y in enumerate(ys))
        cost_plat = kuva_cost(rolls, k) * kuva_value
        net = exp_max - current - cost_plat
        curve.append({"tries": k, "expected": round(exp_max), "kuva": kuva_cost(rolls, k), "net": round(net, 1)})
        if net > best_net:
            best_net, best_n = net, k
    first = curve[0]
    good = _good_stats(market)
    mine_slugs = {s["slug"] for s in view.get("stats", [])}
    my_good = [s["slug"] for s in view.get("stats", []) if s.get("positive") and s["slug"] in good]
    example, example_good = _example(market, good, mine_slugs)
    p_better = sum(1 for v in vals if v > current * 1.1) / n
    verdict = "rolear" if best_n and best_net >= MIN_GAIN else "no"
    return {
        "current": current, "confidence": cur["confidence"],
        "verdict": verdict, "tries": best_n, "net": round(best_net), "kuva": curve[best_n - 1]["kuva"] if best_n else 0,
        "expected": curve[best_n - 1]["expected"] if best_n else current,
        "next_kuva": KUVA_COSTS[min(rolls, len(KUVA_COSTS) - 1)], "first_net": first["net"],
        "p_better": round(p_better * 100), "typical": round(_percentile(vals, 0.5)), "top": round(_percentile(vals, 0.9)),
        "no_ref": round(no_ref / SAMPLES * 100), "rolls": rolls, "kuva_plat": kuva_plat,
        "my_good": my_good, "example": example, "example_good": example_good,
    }
