"""Calibración del estimado por arma contra ventas reales (Factor por arma).

La idea (pedido de Fran, 2026-10-31): el estimador puede estar sistemáticamente
alto o bajo en un arma concreta. Para cada arma se mide la mediana del error en
escala log -- log(estimado / precio pagado) -- y se guarda un factor que corrige
ese sesgo. Con pocas ventas el factor se encoge hacia 1: sólo pesa lo que
alcanzan los datos.

Lo usan los dos lados: el proceso de la nube (tools/estimator_job.py) lo ajusta
con todas las ventas, y la app lo aplica en pricing.estimate.

Sin dependencias: sólo stdlib, así el mismo archivo corre en la Lambda.
"""
import json
import math
from pathlib import Path

# Con menos de MIN_SALES ventas el arma no se toca: el ruido tapa la señal
# (elegido con la grilla de tools/estimator_job.py sobre 12 mil ventas).
MIN_SALES = 10
# Ventas necesarias para que el factor valga la mitad de lo medido.
SHRINK_K = 10
# Tope del factor: una arma rara no puede mover el precio más que esto.
CAP = 1.6
# Por arma se usan como mucho estas ventas (las más nuevas): más no cambia la mediana.
MAX_PER_WEAPON = 80


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


def lookup(levels, weapon, rtype):
    """El nivel más específico que tenga factor para esa arma (nunca se suman)."""
    for level, key in (("por_arma", weapon), ("por_tipo", rtype), ("todo", "*")):
        e = (levels.get(level) or {}).get(key) if levels else None
        if e:
            return level, e
    return None, None


def apply(est, levels, weapon, rtype=None):
    """Multiplica el estimado por el factor que corresponda. est se modifica y se devuelve."""
    if not est or not weapon or not levels:
        return est
    _nivel, e = lookup(levels, weapon, rtype)
    if not e:
        return est
    f = e.get("f") or 1.0
    if abs(f - 1) < 0.01:      # corrección despreciable: no vale ensuciar la tarjeta
        return est
    for k in ("price", "low", "high"):
        if isinstance(est.get(k), (int, float)) and est[k]:
            est[k] = max(1, round(est[k] * f))
    est.setdefault("reasons", []).append({"key": "calibrado", "f": round(f, 2), "n": e.get("n")})
    return est


def load(path):
    """Factores publicados (JSON {'factors': {...}}). Si falta o está roto, {}."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    f = d.get("factors") if isinstance(d, dict) else None
    return f if isinstance(f, dict) else {}


def dump(factors, path, **meta):
    """Escribe el JSON publicado. atomic (tmp + replace) para que la app nunca lea a medias."""
    d = {"v": meta.pop("v", 1), "factors": factors, **meta}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)
    return d
