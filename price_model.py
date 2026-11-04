"""Modelo de precio entrenado con las ventas reales (lo que se pagó, no lo que se pide).

La nube lo entrena cada día con las ventas de Mongo (tools/price_model_job.py, Lambda
riven-stock-price-model) y deja price_model.json en el bucket público solo si, medido
contra ventas que no usó, le gana al estimado por publicaciones. La app lo baja como
weapon_data.json y lo evalúa acá en Python puro: los árboles vienen exportados, así que
no hace falta instalar lightgbm. Si falta, no valida o venció, pricing sigue con el
estimado de siempre.
"""
import datetime as _dt
import json as _json
import math as _math
import time as _time
from pathlib import Path as _Path

URL = "https://riven-stock-estimator-public-099572291636.s3.us-east-1.amazonaws.com/price_model.json"
SCHEMA = 1
# Versión de features(): el job la graba en el archivo y la app no usa un modelo armado con
# otra. Cambiar features() obliga a subirla.
FEATURES_VERSION = 1
# Más viejo que esto no se usa: si el job deja de publicar (no mejora o falla), en dos
# semanas se vuelve al estimado por publicaciones.
MAX_AGE_DAYS = 14
MIN_TREES = 50
_MISSING = {"None": 0, "Zero": 1, "NaN": 2}

_cache = {"mtime": None, "checked": 0.0, "model": None}
_path_override = None
_refresh_hook = None


def set_path(p):
    global _path_override
    _path_override = _Path(p)


def path():
    return _path_override or (_Path(__file__).parent / "data" / "price_model.json")


def reload():
    """Recién bajado: que el próximo estimado relea el archivo sin esperar el minuto del caché."""
    _cache["checked"] = 0.0


def set_refresh_hook(fn):
    """La app registra acá cómo bajar price_model.json (en un hilo: nunca frena el estimado)."""
    global _refresh_hook
    _refresh_hook = fn


# --- Features (las mismas en el entrenamiento y en la app) ---------------------------

def features(weapon, rtype, stats, rolls, rank, enc):
    """stats: [(slug, valor, positivo)]. enc: codificación por arma del modelo publicado."""
    import pricing   # acá y no arriba: pricing importa este módulo
    pos = [(s, v) for s, v, p in stats if p]
    neg = [(s, v) for s, v, p in stats if not p]
    rf = pricing._max_rank_factor(rank)
    f = rf / pricing._config_bonus(len(pos), bool(neg))
    d = {"+" + s: abs(v) * f for s, v in pos}
    for s, v in neg:
        d["-" + s] = abs(v) * rf
    d["npos"] = len(pos)
    d["hasneg"] = int(bool(neg))
    d["rolls"] = _math.log1p(rolls or 0)
    d["rank8"] = int((rank or 0) >= 8)
    base = enc["types"].get(rtype, enc["gmed"])
    w = enc["weapons"].get(weapon)
    d["wenc"] = w[0] if w else base
    d["wq75"] = w[1] if w else d["wenc"]
    d["wn"] = w[2] if w else 0.0
    if rtype:
        d["t:" + rtype] = 1
    return d


# --- Árboles exportados -----------------------------------------------------------------

def export_trees(dump):
    """Booster.dump_model() de lightgbm -> listas compactas que evalúa predict_log().

    Cada árbol: [feature, umbral, izq, der, default_izq, missing, hojas]; los hijos >= 0
    son nodos y los negativos son hojas (~índice)."""
    out = []
    for t in dump["tree_info"]:
        feat, thr, left, right, dleft, miss, leaves = [], [], [], [], [], [], {}

        def walk(n):
            if "leaf_value" in n:
                leaves[n.get("leaf_index", 0)] = round(n["leaf_value"], 9)
                return ~n.get("leaf_index", 0)
            if n["decision_type"] != "<=":
                raise ValueError("decisión no numérica: " + str(n["decision_type"]))
            i = n["split_index"]
            while len(feat) <= i:
                for a in (feat, thr, left, right, dleft, miss):
                    a.append(0)
            feat[i], thr[i] = n["split_feature"], n["threshold"]
            dleft[i], miss[i] = int(bool(n["default_left"])), _MISSING[n["missing_type"]]
            left[i] = walk(n["left_child"])
            right[i] = walk(n["right_child"])
            return i

        walk(t["tree_structure"])
        out.append([feat, thr, left, right, dleft, miss, [leaves[k] for k in range(len(leaves))]])
    return out


def _tree(t, x):
    feat, thr, left, right, dleft, miss, leaves = t
    if not feat:
        return leaves[0]
    i = 0
    while i >= 0:
        v = x[feat[i]]
        m = miss[i]
        if (m == 1 and abs(v) <= 1e-35) or (m == 2 and v != v):
            i = left[i] if dleft[i] else right[i]
        else:
            i = left[i] if v <= thr[i] else right[i]
    return leaves[~i]


def bias_for(bias, y):
    """Corrección por tramo del precio predicho (log): [[techo_del_tramo, corrección], ...]."""
    for edge, corr in bias:
        if edge is None or y <= edge:
            return corr
    return 0.0


def predict_log(model, d):
    """Log del precio para un dict de features (las que el modelo no conoce no cuentan)."""
    ix = model["ix"]
    x = [0.0] * len(ix)
    for k, v in d.items():
        j = ix.get(k)
        if j is not None:
            x[j] = float(v)
    y = sum(_tree(t, x) for t in model["trees"])
    return y + bias_for(model["bias"], y)


def predict(weapon, rtype, view, model=None):
    """Precio que predice el modelo vigente para una vista de riven, o None si no hay modelo
    (o no aplica: sin stats positivos)."""
    model = model or current()
    if not model or not weapon:
        return None
    stats = [(s["slug"], s["value"], s["positive"]) for s in view.get("stats") or []]
    if not any(p for _, _, p in stats):
        return None
    key = (weapon, rtype, tuple(stats), view.get("rolls") or 0, view.get("rank"))
    memo = model["memo"]
    if key not in memo:
        if len(memo) > 5000:
            memo.clear()
        d = features(weapon, rtype, stats, view.get("rolls"), view.get("rank"), model["enc"])
        memo[key] = max(1, round(_math.exp(predict_log(model, d))))
    return memo[key]



def explain(weapon, rtype, view, model=None, top=5, min_pct=3):
    """Qué empuja el precio que predice el modelo: cuánto cambia la predicción (en %) sin cada
    stat, sin los rolls o con el otro rango (máximo <-> sin subir). Es una aproximación por
    ablación (los árboles exportados solo traen hojas), no un reparto exacto que sume el total.
    [{"kind": "stat"|"rolls"|"rank", "slug", "positive", "pct"}], de mayor a menor efecto."""
    model = model or current()
    if not model or not weapon:
        return []
    stats = [(s["slug"], s["value"], s["positive"]) for s in view.get("stats") or []]
    if not any(p for _, _, p in stats):
        return []
    rolls, rank = view.get("rolls") or 0, view.get("rank")
    d = features(weapon, rtype, stats, rolls, rank, model["enc"])
    base = predict_log(model, d)
    out = []

    def add(alt, **kw):
        pct = round((_math.exp(base - predict_log(model, alt)) - 1) * 100)
        if abs(pct) >= min_pct:
            out.append({**kw, "pct": pct})

    for slug, _v, pos in stats:
        alt = dict(d)
        alt[("+" if pos else "-") + slug] = 0.0
        add(alt, kind="stat", slug=slug, positive=pos)
    if rolls:
        add({**d, "rolls": 0.0}, kind="rolls")
    if rank is not None:
        add(features(weapon, rtype, stats, rolls, 0 if rank >= 8 else 8, model["enc"]), kind="rank", rank8=rank >= 8)
    out.sort(key=lambda x: -abs(x["pct"]))
    return out[:top]

# --- Archivo publicado ------------------------------------------------------------------

def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and _math.isfinite(v)


def _ints(a):
    return isinstance(a, list) and all(isinstance(v, int) and not isinstance(v, bool) for v in a)


def _check_tree(t, nfeat):
    feat, thr, left, right, dleft, miss, leaves = t
    n = len(feat)
    if not (_ints(feat) and _ints(left) and _ints(right) and _ints(dleft) and _ints(miss)
            and isinstance(thr, list) and isinstance(leaves, list)):
        return False
    if not (len(thr) == len(left) == len(right) == len(dleft) == len(miss) == n and len(leaves) == n + 1):
        return False
    if not all(_num(v) for v in thr) or not all(_num(v) for v in leaves):
        return False
    if not all(0 <= f < nfeat for f in feat) or not all(m in (0, 1, 2) for m in miss):
        return False
    # hijos: nodos posteriores (sin ciclos) u hojas que existen
    for i in range(n):
        for c in (left[i], right[i]):
            if (c >= 0 and not i < c < n) or (c < 0 and not 0 <= ~c <= n):
                return False
    return True


def check(d):
    """Valida el documento publicado. Devuelve el modelo listo para predecir o None."""
    try:
        if d.get("schema") != SCHEMA or d.get("features_version") != FEATURES_VERSION:
            return None
        updated = _dt.datetime.strptime(d["updated"], "%Y-%m-%dT%H:%M:%SZ")
        cols, trees, enc, bias = d["features"], d["trees"], d["enc"], d["bias"]
        if not (isinstance(cols, list) and cols and all(isinstance(c, str) for c in cols)
                and len(set(cols)) == len(cols)):
            return None
        if not (isinstance(trees, list) and len(trees) >= MIN_TREES
                and all(isinstance(t, list) and len(t) == 7 and _check_tree(t, len(cols)) for t in trees)):
            return None
        if not (_num(enc["gmed"]) and isinstance(enc["types"], dict) and all(_num(v) for v in enc["types"].values())
                and isinstance(enc["weapons"], dict)
                and all(isinstance(v, list) and len(v) == 3 and all(_num(x) for x in v) for v in enc["weapons"].values())):
            return None
        if not (isinstance(bias, list) and all(isinstance(b, list) and len(b) == 2 and (b[0] is None or _num(b[0]))
                                               and _num(b[1]) and abs(b[1]) < 1 for b in bias)):
            return None
        return {"ix": {c: i for i, c in enumerate(cols)}, "trees": trees, "enc": enc, "bias": bias,
                "updated": updated, "memo": {}}
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def fresh(updated, now=None):
    now = now or _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
    return now - updated <= _dt.timedelta(days=MAX_AGE_DAYS)


def current():
    """El modelo vigente (bajado de la nube y validado) o None."""
    now = _time.time()
    if now - _cache["checked"] > 60:   # se llama por cada riven: no mirar el disco cada vez
        _cache["checked"] = now
        p = path()
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = None
        if mtime != _cache["mtime"]:
            model = None
            if mtime:
                try:
                    model = check(_json.loads(p.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    model = None
            _cache.update(mtime=mtime, model=model)
        if _refresh_hook and (mtime is None or now - mtime > 24 * 3600):
            try:
                _refresh_hook()
            except Exception:  # noqa: BLE001 -- bajarlo nunca puede romper un estimado
                pass
    m = _cache["model"]
    return m if m and fresh(m["updated"]) else None
