"""Proceso nocturno de calibración del estimador (el que corre en la nube).

Mide el error del estimado contra las ventas reales y publica un factor de
corrección por nivel: todo el mercado, cada tipo de arma y cada arma. Antes de
publicar se auto-valida: ajusta con las ventas viejas y prueba con las nuevas.
Un nivel sólo se publica si en la prueba baja el error típico, el sesgo no se
aleja de cero y los aciertos dentro de x1.5 no caen más de MAX_OK_DROP; si no,
queda en 1 y la app no cambia nada. Lo aprobado se reajusta con todas las ventas
para publicar: la prueba valida el método, y el factor final aprovecha lo más nuevo.

Uso:
  python tools/estimator_job.py            # con la caché del backtest (prueba local)
  python tools/estimator_job.py --mongo    # con las ventas de Mongo, sin publicar nada

Publicar es de la Lambda (tools/estimator_lambda/handler.py).
"""
import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import calibration  # noqa: E402
import pricing  # noqa: E402

LEVELS = ("por_arma", "por_tipo", "todo")
# Fracción de la ventana que se usa para entrenar (el resto valida).
TRAIN_FRAC = 0.6
# Los aciertos dentro de x1.5 son secundarios: corregir el centro a veces estira apenas
# la cola, así que se toleran estos puntos de caída pero no más.
MAX_OK_DROP = 0.02


def _median(xs):
    a = sorted(xs)
    n = len(a)
    if not n:
        return 0.0
    return a[n // 2] if n % 2 else (a[n // 2 - 1] + a[n // 2]) / 2


def stats(errs):
    """(n, mediana |err|, % dentro de x1.5, sesgo) en escala log."""
    if not errs:
        return {"n": 0, "med": 0.0, "ok": 0.0, "bias": 0.0}
    a = sorted(abs(e) for e in errs)
    return {"n": len(errs), "med": a[len(a) // 2],
            "ok": sum(x <= math.log(1.5) for x in a) / len(a), "bias": _median(errs)}


def fit_levels(cases):
    """cases: [(arma, tipo, t, err_log)] -> {'por_arma': {...}, 'por_tipo': {...}, 'todo': {...}}"""
    out = {}
    for level in LEVELS:
        groups = {}
        for weapon, rtype, _t, e in cases:
            key = {"por_arma": weapon, "por_tipo": rtype, "todo": "*"}[level]
            if key:
                groups.setdefault(key, []).append(e)
        out[level] = calibration.fit(groups)
    return out


def lookup(factors, weapon, rtype):
    """El nivel más específico que tenga factor para esa arma (nunca se suman)."""
    return calibration.lookup(factors, weapon, rtype)


def evaluate(cases, factors):
    """Aplica los factores (sin cambiarlos) y devuelve stats + cuántas usaron cuál."""
    errs, usados = [], {}
    for weapon, rtype, _t, e in cases:
        level, f = lookup(factors, weapon, rtype)
        if f:
            e = e + math.log(f["f"])
            usados[level] = usados.get(level, 0) + 1
        errs.append(e)
    return stats(errs), usados


def choose(train, test):
    """Elige los niveles a publicar según la prueba (datos que no vio). Devuelve
    (factores reajustados con todas las ventas, informe medido sólo con train)."""
    fitted = fit_levels(train)
    base, _ = evaluate(test, {})
    factors, report = {}, {"antes": base, "niveles": {}}
    for level in LEVELS:
        cand = dict(factors)
        cand[level] = fitted[level]
        got, usados = evaluate(test, cand)
        # Corregir un sesgo tiene que bajar el error típico sin alejar el sesgo de cero.
        mejor = (got["med"] < base["med"] * 0.995 and abs(got["bias"]) <= abs(base["bias"]) + 1e-9
                 and got["ok"] >= base["ok"] - MAX_OK_DROP and got["n"] > 0)
        report["niveles"][level] = {"fitted": len(fitted[level]), "test": got, "usados": usados.get(level, 0), "publica": mejor}
        if mejor:
            factors[level] = fitted[level]
            base = got
    report["despues"] = base
    final = fit_levels(train + test)
    return {level: final[level] for level in factors}, report


def split(cases, frac=TRAIN_FRAC):
    """Corte temporal: entrena con lo viejo, valida con lo nuevo."""
    cs = sorted(cases, key=lambda c: c[2])
    cut = cs[min(len(cs) - 1, int(len(cs) * frac))][2]
    return [c for c in cs if c[2] < cut], [c for c in cs if c[2] >= cut]


def publish_shape(factors, report, now=None):
    """El documento que se publica y que la app lee."""
    return {
        "v": 1,
        "updated": (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "factors": {lvl: f for lvl, f in factors.items() if f},
        "validated": {lvl: bool(r.get("publica")) for lvl, r in (report.get("niveles") or {}).items()},
        "pricing_sha": calibration.code_sha(pricing.__file__),
    }


def cases_from_cache(path):
    """Casos desde la caché del backtest (para probar sin Mongo)."""
    from tools.backtest_estimate import cases as backtest_cases
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for s, view, market, rtype in backtest_cases(data):
        est = pricing.estimate(view, market, rtype=rtype, weapon=s["weapon"])
        if est and est.get("price"):
            out.append((s["weapon"], rtype, s["t"], math.log(est["price"] / s["price"])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(ROOT / "cache" / "backtest.json"))
    ap.add_argument("--mongo", action="store_true", help="usar Mongo (lo que corre en la nube)")
    a = ap.parse_args()
    if a.mongo:
        import estimator_mongo
        cases = estimator_mongo.cases_from_mongo()
    else:
        cases = cases_from_cache(a.cache)
    train, test = split(cases)
    factors, report = choose(train, test)
    doc = publish_shape(factors, report)
    print(f"{len(cases)} ventas; entrenamiento {len(train)}, prueba {len(test)}")
    for level in LEVELS:
        r = report["niveles"][level]
        t, b = r["test"], report["antes"]
        print(f"{level:>8}: {r['fitted']:>4} factores, {r['usados']:>5} ventas del test lo usan, "
              f"{'PUBLICA' if r['publica'] else 'no'}  med {math.exp(b['med']):.2f}x -> {math.exp(t['med']):.2f}x, "
              f"aciertos {b['ok']*100:.1f}% -> {t['ok']*100:.1f}%")
    print(f"total: med {math.exp(report['antes']['med']):.2f}x -> {math.exp(report['despues']['med']):.2f}x "
          f"({len(doc['factors'])} niveles publicados)")
    return doc


if __name__ == "__main__":
    main()
