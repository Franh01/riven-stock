"""Publica una versión: python tools/release.py 0.2.0 [--dry-run]

Pasos: valida que el árbol esté limpio y el CHANGELOG tenga la sección, actualiza VERSION,
mueve "Sin publicar" a la nueva versión, arma el zip (solo código, sin datos del usuario),
calcula el sha256, hace commit + tag + push y crea el release en GitHub con `gh`.
Las notas del release salen de la sección del CHANGELOG.
"""
import hashlib
import re
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUIR = ["app.py", "orders.py", "pricing.py", "store.py", "wfm_client.py", "updater.py", "requirements.txt",
           "VERSION", "CHANGELOG.md", "README.md", "instalar.bat", "assets", "data", "tools", "ui"]


def run(*cmd, capture=False):
    r = subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=capture)
    return r.stdout.strip() if capture else ""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if len(args) != 1 or not re.fullmatch(r"\d+\.\d+\.\d+", args[0]):
        sys.exit("Uso: python tools/release.py X.Y.Z [--dry-run]")
    ver = args[0]
    if not dry and run("git", "status", "--porcelain", capture=True).replace("?? ", "").strip():
        # Archivos sin commitear (salvo ignorados) harían un release que no coincide con el repo.
        sys.exit("Hay cambios sin commitear. Commiteá primero.")

    cl = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"## \[Sin publicar\]\n(.*?)(?=\n## \[)", cl, re.S)
    notas = m.group(1).strip() if m else ""
    if not notas:
        sys.exit("La sección [Sin publicar] del CHANGELOG está vacía.")
    cl = cl.replace("## [Sin publicar]\n", f"## [Sin publicar]\n\n## [{ver}] - {date.today()}\n", 1)

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    zpath = dist / f"riven-stock-v{ver}.zip"
    if not dry:
        (ROOT / "CHANGELOG.md").write_text(cl, encoding="utf-8")
        (ROOT / "VERSION").write_text(ver + "\n", encoding="utf-8")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre in INCLUIR:
            p = ROOT / nombre
            archivos = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
            for f in archivos:
                if "__pycache__" in f.parts:
                    continue
                rel = f.relative_to(ROOT).as_posix()
                if rel == "VERSION":
                    z.writestr(rel, ver + "\n")
                elif rel == "CHANGELOG.md":
                    z.writestr(rel, cl)
                else:
                    z.write(f, rel)
    sha = hashlib.sha256(zpath.read_bytes()).hexdigest()
    shafile = dist / (zpath.name + ".sha256")
    shafile.write_text(f"{sha}  {zpath.name}\n")
    print(f"Paquete: {zpath} ({zpath.stat().st_size // 1024} KB)\nsha256: {sha}")
    if dry:
        print("--dry-run: no se tocó el repo ni se publicó nada.")
        return

    run("git", "add", "VERSION", "CHANGELOG.md")
    run("git", "commit", "-m", f"Version {ver}\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>")
    run("git", "tag", f"v{ver}")
    run("git", "push", "origin", "HEAD", f"v{ver}")
    run("gh", "release", "create", f"v{ver}", str(zpath), str(shafile),
        "--title", f"Riven Stock {ver}", "--notes", notas)
    print(f"Release v{ver} publicado.")


if __name__ == "__main__":
    main()
