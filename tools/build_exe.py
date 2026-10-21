"""Arma el instalador para Windows sin Python: python tools/build_exe.py
Genera dist/RivenStock-vX.Y.Z-Setup.exe y su .sha256. Necesita pyinstaller e Inno Setup 6."""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def iscc():
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
        p = Path(base) / "Programs" / "Inno Setup 6" / "ISCC.exe" if base == os.environ.get("LOCALAPPDATA") else Path(base) / "Inno Setup 6" / "ISCC.exe"
        if p.exists():
            return str(p)
    sys.exit("No se encontró Inno Setup 6 (winget install JRSoftware.InnoSetup).")


def main():
    ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    build = ROOT / "build"
    shutil.rmtree(build, ignore_errors=True)
    py = ROOT / ".venv" / "Scripts" / "python.exe"   # el venv de la app tiene todas las dependencias
    py = str(py) if py.exists() else sys.executable
    subprocess.run([py, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(build / "dist"),
                    "--workpath", str(build / "work"), str(ROOT / "installer" / "riven_stock.spec")], cwd=ROOT, check=True)
    subprocess.run([iscc(), f"/DAppVersion={ver}", str(ROOT / "installer" / "riven_stock.iss")], cwd=ROOT, check=True)
    setup = ROOT / "dist" / f"RivenStock-v{ver}-Setup.exe"
    sha = hashlib.sha256(setup.read_bytes()).hexdigest()
    (setup.parent / (setup.name + ".sha256")).write_text(f"{sha}  {setup.name}\n")
    print(f"Instalador: {setup} ({setup.stat().st_size // 1024} KB)\nsha256: {sha}")


if __name__ == "__main__":
    main()
