"""Publica una versión: python tools/release.py 0.2.0 [--dry-run]

Pasos: valida que el árbol esté limpio y el CHANGELOG tenga la sección, actualiza VERSION,
mueve "Sin publicar" a la nueva versión, arma el zip (solo código, sin datos del usuario),
calcula el sha256, hace commit + tag + push y crea el release en GitHub con `gh`.
Las notas del release salen de la sección del CHANGELOG.
"""
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUIR = ["app.py", "cloud_backup.py", "cloudapi.py", "crashes.py", "loops.py", "feedback.py", "feedbackapi.py", "loophealth.py", "netdiag.py", "opportunities.py", "ratelimit.py", "stockcheck.py", "orders.py", "pricing.py", "reroll.py", "store.py", "wfm_client.py", "updater.py", "requirements.txt",
           "VERSION", "CHANGELOG.md", "README.md", "instalar.bat", "assets", "data", "tools", "ui", "installer"]


def run(*cmd, capture=False):
    r = subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=capture)
    return r.stdout.strip() if capture else ""


def ci_en_verde(timeout=1800):
    """True si el workflow 'CI Windows' del commit actual (ya pusheado) terminó en success.
    Espera hasta `timeout` s a que termine. Usa la API pública de GitHub: el repo es público y no hace falta gh."""
    sha = run("git", "rev-parse", "HEAD", capture=True)
    repo = re.search(r"github\.com[:/](.+?)(?:\.git)?$", run("git", "remote", "get-url", "origin", capture=True)).group(1)
    url = f"https://api.github.com/repos/{repo}/actions/runs?head_sha={sha}"
    fin = time.time() + timeout
    while True:
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                runs = [w for w in json.load(r)["workflow_runs"] if w["name"] == "CI Windows"]
        except OSError as e:
            sys.exit(f"No pude consultar el CI de GitHub: {e}")
        if not runs:
            print(f"No hay CI para {sha[:7]}: pusheá el commit y esperá a que corra.")
            return False
        w = runs[0]
        if w["status"] == "completed":
            print(f"CI Windows de {sha[:7]}: {w['conclusion']} ({w['html_url']})")
            return w["conclusion"] == "success"
        if time.time() > fin:
            print("El CI sigue corriendo y se agotó la espera.")
            return False
        print(f"CI Windows de {sha[:7]} en curso ({w['status']}), espero...")
        time.sleep(30)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if len(args) != 1 or not re.fullmatch(r"\d+\.\d+\.\d+", args[0]):
        sys.exit("Uso: python tools/release.py X.Y.Z [--dry-run]")
    ver = args[0]
    if not dry and run("git", "status", "--porcelain", capture=True).replace("?? ", "").strip():
        # Archivos sin commitear (salvo ignorados) harían un release que no coincide con el repo.
        sys.exit("Hay cambios sin commitear. Commiteá primero.")

    if not dry and not ci_en_verde():
        sys.exit("El CI de Windows de este commit no está en verde; no se publica. Esperá a que termine o corregí el error.")

    if subprocess.run([sys.executable, "tools/check_js.py"], cwd=ROOT).returncode:
        sys.exit("El JS de la interfaz tiene errores de sintaxis; no se publica.")

    if subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT).returncode:
        sys.exit("Fallan los tests; no se publica.")

    cl = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"## \[Sin publicar\]\n(.*?)(?=\n## \[)", cl, re.S)
    notas = m.group(1).strip() if m else ""
    if not notas:
        sys.exit("La sección [Sin publicar] del CHANGELOG está vacía.")
    cl = cl.replace("## [Sin publicar]\n", f"## [Sin publicar]\n\n## [{ver}] - {date.today()}\n", 1)

    if not dry:   # tabla de armas al día en cada release; si no hay internet se publica la que ya está
        try:
            run(sys.executable, "tools/build_weapon_data.py")
        except subprocess.CalledProcessError:
            print("Aviso: no se pudo actualizar data/weapon_stats.json; se usa la anterior.")
        try:   # etiqueta caro/barato: reentrena con las ventas de la nube; si falla se publica el modelo anterior
            ventas = ROOT / "dist" / "ventas.json"
            ventas.parent.mkdir(exist_ok=True)
            run("node", "tools/export_sales.js", str(ventas))
            run(sys.executable, "tools/train_tier.py", str(ventas))
        except (subprocess.CalledProcessError, OSError):
            print("Aviso: no se pudo reentrenar data/tier_model.json; se usa el anterior.")
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

    # Instalador para Windows sin Python (PyInstaller + Inno Setup), con el VERSION ya actualizado.
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    run(str(py if py.exists() else sys.executable), "tools/build_exe.py")
    setup = dist / f"RivenStock-v{ver}-Setup.exe"
    setupsha = dist / (setup.name + ".sha256")

    run("git", "add", "VERSION", "CHANGELOG.md", "data/weapon_stats.json", "data/tier_model.json")
    run("git", "commit", "-m", f"Version {ver}\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>")
    run("git", "tag", f"v{ver}")
    run("git", "push", "origin", "HEAD", f"v{ver}")
    run("gh", "release", "create", f"v{ver}", str(zpath), str(shafile), str(setup), str(setupsha),
        "--title", f"Riven Stock {ver}", "--notes", notas)
    print(f"Release v{ver} publicado.")


if __name__ == "__main__":
    main()
