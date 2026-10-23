"""Reporte de crashes y salud tras actualizar. Solo biblioteca estándar: se importa antes de configurar el log.

Carpeta `crashes/` en los datos: crash-<fecha>.txt (pendientes de enviar), running.lock (la sesión sigue o murió)
y health.json (última versión sana y cuántos arranques seguidos fallaron por versión)."""
import ctypes
import json
import os
import shutil
import threading
import time
import traceback
from pathlib import Path

GOOD_AFTER_S = 60      # una sesión que aguanta este tiempo marca su versión como sana
STREAK_TO_OFFER = 2    # fallos seguidos de una versión nueva para ofrecer volver a la sana
MAX_PENDING = 5

_dir = None
_version = "?"


def _read(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p, data):
    try:
        Path(p).write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def _alive(pid):
    """¿Sigue vivo ese proceso? (Windows). Ante la duda, no."""
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))   # QUERY_LIMITED_INFORMATION
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    except Exception:
        return False


def begin(data_dir, log_file, version):
    """Llamar antes de que el log se pise. Si la sesión anterior no cerró limpia, la guarda como crash pendiente."""
    global _dir, _version
    _dir, _version = Path(data_dir) / "crashes", version
    try:
        _dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        _dir = None
        return
    lock = _dir / "running.lock"
    old = _read(lock, {}) if lock.exists() else None
    if old is not None and old.get("pid") != os.getpid() and old.get("pid") and _alive(old["pid"]):
        _dir = None   # otra instancia sigue abierta: no es un crash, y esta no toca su lock ni lo borra al cerrar
        return
    if old is not None:
        prev = old.get("v", "?")
        h = _read(_dir / "health.json", {})
        h.setdefault("streak", {})[prev] = h.get("streak", {}).get(prev, 0) + 1
        _write(_dir / "health.json", h)
        try:
            tail = Path(log_file).read_bytes()[-60000:].decode("utf-8", "replace")
        except OSError:
            tail = ""
        _save("La sesión anterior terminó sin cerrar bien (se cerró de golpe o falló).", tail, prev)
    _write(lock, {"v": version, "t": time.time(), "pid": os.getpid()})
    threading.Timer(GOOD_AFTER_S, _mark_good).start()


def _mark_good():
    if _dir:
        h = _read(_dir / "health.json", {})
        h["good"] = _version
        h.setdefault("streak", {})[_version] = 0
        _write(_dir / "health.json", h)


def end():
    """Cierre limpio."""
    if _dir:
        try:
            (_dir / "running.lock").unlink()
        except OSError:
            pass


def _save(kind_line, body, version=None):
    if not _dir:
        return
    files = sorted(_dir.glob("crash-*.txt"))
    for old in files[:max(0, len(files) - MAX_PENDING + 1)]:
        old.unlink(missing_ok=True)
    name = _dir / f"crash-{time.strftime('%Y%m%d-%H%M%S')}-{len(files) % 100:02d}.txt"
    try:
        name.write_text(f"version: {version or _version}\n{kind_line}\n\n{body}", encoding="utf-8")
    except OSError:
        pass


def record(where, exc_info):
    """Un error no controlado (Python o de la interfaz): queda como pendiente."""
    t, v, tb = exc_info
    _save(f"Error no controlado en {where}.", "".join(traceback.format_exception(t, v, tb)))


def record_text(where, text):
    _save(f"Error no controlado en {where}.", text)


def pending():
    if not _dir:
        return []
    return sorted(_dir.glob("crash-*.txt"))


def discard():
    for p in pending():
        p.unlink(missing_ok=True)


def rollback_target():
    """Versión sana a la que volver, si la actual viene fallando seguido; si no, None."""
    if not _dir:
        return None
    h = _read(_dir / "health.json", {})
    good = h.get("good")
    if good and good != _version and h.get("streak", {}).get(_version, 0) >= STREAK_TO_OFFER:
        return good
    return None
