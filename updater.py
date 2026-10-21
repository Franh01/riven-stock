"""Autoactualización: consulta GitHub Releases, descarga, verifica y reemplaza los archivos.

Dos partes:
- Funciones que usa la app (version_actual, buscar_actualizacion, preparar, lanzar_aplicador).
- Modo `--aplicar`: corre como proceso aparte (copiado fuera de la carpeta de la app), espera a
  que la app cierre, reemplaza los archivos con backup y rollback, y la vuelve a abrir.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import requests

REPO = "Franh01/riven-stock"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
FROZEN = getattr(sys, "frozen", False)   # instalado con el Setup.exe (sin Python)
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

# Nunca se pisan ni se borran: datos del usuario y entorno local.
PRESERVAR = {".env", ".venv", "cache", "_backup", ".git", "__pycache__", "riven_stock.db",
             "riven_stock.db-wal", "riven_stock.db-shm"}


def version_actual(app_dir=APP_DIR):
    try:
        return (Path(app_dir) / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def _tupla(v):
    partes = []
    for p in v.lstrip("vV").split("."):
        try:
            partes.append(int(p))
        except ValueError:
            partes.append(0)
    return tuple(partes)


def buscar_actualizacion(timeout=10):
    """Devuelve {version, notas, zip_url, sha_url} si hay una versión más nueva, o None."""
    r = requests.get(API, timeout=timeout, headers={"Accept": "application/vnd.github+json"})
    if r.status_code == 404:          # todavía no hay releases
        return None
    r.raise_for_status()
    rel = r.json()
    nueva = rel["tag_name"].lstrip("vV")
    if _tupla(nueva) <= _tupla(version_actual()):
        return None
    zip_url = sha_url = None
    paquete = "Setup.exe" if FROZEN else ".zip"   # instalado se actualiza con el instalador; con Python, con el zip
    for a in rel.get("assets", []):
        if a["name"].endswith(paquete):
            zip_url = a["browser_download_url"]
        elif a["name"].endswith(paquete + ".sha256"):
            sha_url = a["browser_download_url"]
    if not zip_url or not sha_url:
        return None                   # release sin los assets esperados: no se ofrece
    return {"version": nueva, "notas": rel.get("body") or "", "zip_url": zip_url, "sha_url": sha_url}


def preparar(info, timeout=60):
    """Descarga el zip, verifica el sha256 y lo extrae. Devuelve la carpeta de staging."""
    staging = Path(tempfile.mkdtemp(prefix="rivenstock_upd_"))
    esperado = requests.get(info["sha_url"], timeout=timeout).text.split()[0].strip().lower()
    zpath = staging / ("RivenStock-Setup.exe" if FROZEN else "paquete.zip")
    h = hashlib.sha256()
    with requests.get(info["zip_url"], timeout=timeout, stream=True) as r:
        r.raise_for_status()
        with open(zpath, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
                h.update(chunk)
    if h.hexdigest() != esperado:
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError("El paquete descargado no coincide con su sha256; no se instala.")
    if FROZEN:
        return staging, zpath
    nuevo = staging / "nuevo"
    with zipfile.ZipFile(zpath) as z:
        z.extractall(nuevo)
    # El zip puede traer todo dentro de una carpeta raíz única.
    hijos = list(nuevo.iterdir())
    if len(hijos) == 1 and hijos[0].is_dir():
        nuevo = hijos[0]
    if not (nuevo / "app.py").exists() or not (nuevo / "VERSION").exists():
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError("El paquete no tiene la estructura esperada.")
    meta = {"nuevo": str(nuevo), "staging": str(staging)}
    (staging / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return staging, nuevo


def lanzar_aplicador(staging, nuevo):
    """Copia este archivo fuera de la app y lo ejecuta aparte. La app debe cerrarse después."""
    if FROZEN:   # el instalador reemplaza los archivos y vuelve a abrir la app
        subprocess.Popen([str(nuevo), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                         creationflags=0x00000008 | 0x00000200, close_fds=True, cwd=str(staging))
        return
    copia = Path(staging) / "aplicar_update.py"
    shutil.copy2(__file__, copia)
    pyw = APP_DIR / ".venv" / "Scripts" / "pythonw.exe"
    exe = str(pyw if pyw.exists() else sys.executable)
    flags = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([exe, str(copia), "--aplicar", str(os.getpid()), str(nuevo), str(APP_DIR)],
                     creationflags=flags, close_fds=True, cwd=str(staging))


# ---------------------------------------------------------------- modo aplicador

def _esperar_pid(pid, limite=60):
    import ctypes
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x00100000, False, pid)   # SYNCHRONIZE
    if h:
        k32.WaitForSingleObject(h, limite * 1000)
        k32.CloseHandle(h)


def _copiar_arbol(origen, destino, creados=None):
    for item in origen.iterdir():
        if item.name in PRESERVAR:
            continue
        d = destino / item.name
        if item.is_dir():
            if creados is not None and not d.exists():
                creados.append(d)
            d.mkdir(exist_ok=True)
            _copiar_arbol(item, d, creados)
        else:
            if creados is not None and not d.exists():
                creados.append(d)
            shutil.copy2(item, d)


def _respaldar(app_dir, backup):
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir()
    for item in app_dir.iterdir():
        if item.name in PRESERVAR or item.name == "node_modules":
            continue
        if item.is_dir():
            shutil.copytree(item, backup / item.name)
        else:
            shutil.copy2(item, backup / item.name)


def _restaurar(app_dir, backup):
    for item in backup.iterdir():
        d = app_dir / item.name
        if item.is_dir():
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(item, d)
        else:
            shutil.copy2(item, d)


def aplicar(pid, nuevo, app_dir):
    nuevo, app_dir = Path(nuevo), Path(app_dir)
    log = app_dir / "cache" / "update.log"
    log.parent.mkdir(exist_ok=True)

    def anotar(msg):
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")

    _esperar_pid(int(pid))
    time.sleep(1)
    backup = app_dir / "_backup"
    creados = []
    vieja = version_actual(app_dir)
    reqs_viejos = (app_dir / "requirements.txt").read_text(encoding="utf-8") \
        if (app_dir / "requirements.txt").exists() else ""
    try:
        _respaldar(app_dir, backup)
        _copiar_arbol(nuevo, app_dir, creados)
        reqs_nuevos = (app_dir / "requirements.txt").read_text(encoding="utf-8") \
            if (app_dir / "requirements.txt").exists() else ""
        py = app_dir / ".venv" / "Scripts" / "python.exe"
        if reqs_nuevos != reqs_viejos and py.exists():
            r = subprocess.run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q",
                                "-r", str(app_dir / "requirements.txt")],
                               capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                raise RuntimeError("pip falló: " + r.stderr[-500:])
        anotar(f"Actualizado {vieja} -> {version_actual(app_dir)}")
    except Exception as e:
        anotar(f"Falló la actualización ({e}); se restaura la versión {vieja}")
        try:
            _restaurar(app_dir, backup)
            # Lo que la version nueva agrego y la vieja no tenia se quita (los mas profundos primero).
            for c in sorted(creados, key=lambda x: len(x.parts), reverse=True):
                if c.is_dir():
                    shutil.rmtree(c, ignore_errors=True)
                else:
                    c.unlink(missing_ok=True)
        except Exception as e2:
            anotar(f"Falló el rollback: {e2}")
    pyw = app_dir / ".venv" / "Scripts" / "pythonw.exe"
    exe = str(pyw if pyw.exists() else sys.executable)
    subprocess.Popen([exe, str(app_dir / "app.py")], cwd=str(app_dir),
                     creationflags=0x00000008 | 0x00000200, close_fds=True)


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--aplicar":
        aplicar(sys.argv[2], sys.argv[3], sys.argv[4])
