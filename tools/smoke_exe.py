"""Prueba de humo del exe de Windows: python tools/smoke_exe.py ruta/RivenStock.exe [segundos]
Lo arranca con datos descartables, lo deja vivir unos segundos y falla si se cierra solo, si el log
trae un error crítico o si nunca llegó a escribir el arranque. Corre en el CI de GitHub (windows-latest)."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main():
    exe = Path(sys.argv[1])
    espera = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    if not exe.exists():
        sys.exit(f"No existe {exe}")
    datos = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "rs-smoke"
    datos.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, RIVEN_STOCK_DATA=str(datos))
    p = subprocess.Popen([str(exe)], env=env)
    time.sleep(espera)
    vivo = p.poll() is None
    if vivo:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    log = datos / "riven-stock.log"
    texto = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    print(texto[-3000:] or "(sin log)")
    if "=== Arranque" not in texto:
        sys.exit("FALLO: el exe no llegó a escribir el arranque en el log.")
    if "CRITICAL" in texto or "La app no pudo arrancar" in texto or "Error sin capturar" in texto:
        sys.exit("FALLO: el log trae un error crítico.")
    if not vivo:
        sys.exit(f"FALLO: el exe se cerró solo antes de {espera} s (código {p.returncode}).")
    print(f"OK: el exe siguió vivo {espera} s sin errores críticos.")


if __name__ == "__main__":
    main()
