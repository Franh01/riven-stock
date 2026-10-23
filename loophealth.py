"""Salud de los bucles de fondo: cada uno anota su último ciclo y su último error, para que se vea en los reportes."""
import threading
import time

_lock = threading.Lock()
_loops = {}


def beat(name, period, err=None):
    """Anota un ciclo del bucle `name` (period = segundos esperados entre ciclos). err = excepción o texto."""
    with _lock:
        s = _loops.setdefault(name, {"period": period, "ok": None, "err": None, "msg": ""})
        s["period"] = period
        if err is None:
            s["ok"] = time.time()
        else:
            s["err"], s["msg"] = time.time(), str(err)[:200]


def report():
    """Texto de una línea por bucle; marca ATRASADO si no hubo ciclo en 5 períodos."""
    now = time.time()
    with _lock:
        out = ["=== Salud de los bucles ==="]
        for n, s in sorted(_loops.items()):
            ok = f"hace {now - s['ok']:.0f}s" if s["ok"] else "nunca"
            late = " ATRASADO" if s["ok"] and now - s["ok"] > 5 * max(s["period"], 60) else ""
            err = f" | último error hace {now - s['err']:.0f}s: {s['msg']}" if s["err"] else ""
            out.append(f"{n}: último ciclo OK {ok}{late}{err}")
        return "\n".join(out) + "\n"
