"""Calibración del estimado por arma contra ventas reales (Factor por arma).

La idea (pedido de Fran, 2026-10-31): el estimador puede estar sistemáticamente
alto o bajo en un arma concreta. Para cada arma se mide la mediana del error en
escala log -- log(estimado / precio pagado) -- y se guarda un factor que corrige
ese sesgo. Con pocas ventas el factor se encoge hacia 1: sólo pesa lo que
alcanzan los datos.

Lo usan los dos lados: el proceso de la nube (tools/estimator_job.py) lo ajusta
con una muestra de las ventas recientes, y la app lo aplica en pricing.estimate.

Sin dependencias: sólo stdlib, así el mismo archivo corre en la Lambda.
"""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

# Archivo público con los factores (cloud/estimator.yml): la app lo baja y release.py lo verifica.
ESTIMATOR_URL = "https://riven-stock-estimator-public-099572291636.s3.us-east-1.amazonaws.com/factors.json"

# Con menos de MIN_SALES ventas el arma no se toca: el ruido tapa la señal.
MIN_SALES = 10
# Ventas necesarias para que el factor valga la mitad de lo medido.
SHRINK_K = 10
# Tope del factor: una arma rara no puede mover el precio más que esto.
CAP = 1.6
# Por arma se usan como mucho estas ventas (las más nuevas): más no cambia la mediana.
MAX_PER_WEAPON = 80
# Factores más viejos que esto no se aplican: si la nube se cae, la app vuelve al estimado puro.
MAX_AGE_DAYS = 7


def factor_entry(logs):
    """logs: [log(estimado / pagado)]. Devuelve {'n', 'med_log', 'f'} o None.

    El factor corrige: si el estimado viene 20 % arriba (med_log = log 1.2),
    multiplicar por 1/1.2 lo deja en su lugar. De ahí el signo negativo."""
    if not logs:
        return None
    a = sorted(logs)
    med = a[len(a) // 2] if len(a) % 2 else (a[len(a) // 2 - 1] + a[len(a) // 2]) / 2
    n = len(a)
    f = math.exp(-med * n / (n + SHRINK_K))    # encogido hacia 1 (med_log = 0)
    f = min(max(f, 1 / CAP), CAP)
    return {"n": n, "med_log": round(med, 4), "f": round(f, 4)}


def fit(samples):
    """samples: {arma: [log(est/pagado)]} -> {arma: entrada} sólo con las que alcanzan."""
    out = {}
    for weapon, logs in samples.items():
        if len(logs) < MIN_SALES:
            continue
        e = factor_entry(logs[-MAX_PER_WEAPON:])
        if e:
            out[weapon] = e
    return out


def _usable(e):
    """(f, n) de una entrada publicada, o None si está rota. Viene de la red y termina
    en un precio y en el HTML: acá se valida lo que en otro caso rompería un estimado."""
    try:
        f, n = float(e["f"]), int(e["n"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(f) or f <= 0:
        return None
    return min(max(f, 1 / CAP), CAP), n


def lookup(levels, weapon, rtype):
    """El nivel más específico que tenga un factor sano para esa arma (nunca se suman)."""
    if not isinstance(levels, dict):
        return None, None
    for level, key in (("por_arma", weapon), ("por_tipo", rtype), ("todo", "*")):
        group = levels.get(level)
        e = group.get(key) if isinstance(group, dict) else None
        if _usable(e):
            return level, e
    return None, None


def apply(est, levels, weapon, rtype=None):
    """Multiplica el estimado por el factor que corresponda. est se modifica y se devuelve."""
    if not est or not weapon or not levels:
        return est
    _nivel, e = lookup(levels, weapon, rtype)
    if not e:
        return est
    f, n = _usable(e)
    if abs(f - 1) < 0.01:      # corrección despreciable: no vale ensuciar la tarjeta
        return est
    for k in ("price", "low", "high"):
        if isinstance(est.get(k), (int, float)) and est[k]:
            est[k] = max(1, round(est[k] * f))
    est.setdefault("reasons", []).append({"key": "calibrado", "f": round(f, 2), "n": n})
    return est


def load(path):
    """Factores publicados: (niveles, fecha de publicación). Si falta o está roto, ({}, None)."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, None
    f = d.get("factors") if isinstance(d, dict) else None
    return (f, d.get("updated")) if isinstance(f, dict) else ({}, None)


def fresh(updated, now=None):
    """¿Siguen vigentes? Sin una fecha válida, no: mejor el estimado puro que uno viejo."""
    try:
        t = dt.datetime.strptime(updated, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return False
    return (now or dt.datetime.now(dt.timezone.utc)) - t <= dt.timedelta(days=MAX_AGE_DAYS)


def code_sha(path):
    """Huella del código, igual en cualquier sistema (no importan los finales de línea).
    La nube mide un pricing.py concreto: release.py compara para no publicar otro distinto."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:12]
