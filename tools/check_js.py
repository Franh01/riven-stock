"""Chequea la sintaxis del JS de la interfaz (scripts embebidos de ui/index.html y ui/*.js) con node.
Un error de sintaxis deja la UI sin arrancar (esqueletos para siempre), así que release.py lo corre antes de publicar.
Uso: python tools/check_js.py   (sale con código 1 si hay error; si no hay node, avisa y sale 0)"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "ui"


def main():
    node = shutil.which("node")
    if not node:
        print("Aviso: node no está instalado; no se chequeó la sintaxis del JS.")
        return 0
    fuentes = [(f.name, f.read_text(encoding="utf-8")) for f in sorted(UI.glob("*.js"))]
    html = (UI / "index.html").read_text(encoding="utf-8")
    for i, b in enumerate(re.findall(r"<script(?![^>]*\bsrc\b)[^>]*>(.*?)</script>", html, re.S)):
        fuentes.append((f"index.html#script{i}", b))
    malos = 0
    with tempfile.TemporaryDirectory() as d:
        for i, (nombre, src) in enumerate(fuentes):
            if not src.strip():
                continue
            p = Path(d) / f"s{i}.js"
            p.write_text(src, encoding="utf-8")
            r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
            if r.returncode:
                malos += 1
                print(f"Error de sintaxis en {nombre}:\n{r.stderr.strip()}")
    if not malos:
        print("JS de la interfaz: sintaxis OK.")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
