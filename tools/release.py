"""Publica una versión: python tools/release.py 0.2.0 [--dry-run]

Corre en cualquier sistema (se usa desde Ubuntu): valida que el árbol esté limpio, que el CI de
Windows del commit esté en verde y que el CHANGELOG tenga la sección; actualiza datos, VERSION y
CHANGELOG, hace commit + tag vX.Y.Z + push y espera a que aparezca el release.
El release lo arma el CI de Windows al recibir el tag (.github/workflows/ci.yml): build del exe e
instalador, prueba de humo, y `python tools/release.py --ci X.Y.Z` para el zip, los sha256 y las
notas; después lo publica con `gh` y el token del workflow. Así no hace falta gh ni Inno Setup local.
--dry-run solo arma el zip en dist/ para revisarlo.
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


def notas_de(cl, ver):
    """Texto de la sección [ver] del CHANGELOG (las notas del release)."""
    m = re.search(rf"## \[{re.escape(ver)}\][^\n]*\n(.*?)(?=\n## \[|\Z)", cl, re.S)
    return m.group(1).strip() if m else ""


def armar_zip(ver, cl):
    """dist/riven-stock-vX.Y.Z.zip (solo código, sin datos del usuario) y su .sha256."""
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    zpath = dist / f"riven-stock-v{ver}.zip"
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
    (dist / (zpath.name + ".sha256")).write_text(f"{sha}  {zpath.name}\n")
    print(f"Paquete: {zpath} ({zpath.stat().st_size // 1024} KB)\nsha256: {sha}")
    return zpath


def modo_ci(ver):
    """Lo llama el CI en el tag vX.Y.Z: zip + sha256 + dist/notas.md con el árbol del tag."""
    actual = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if actual != ver:
        sys.exit(f"El tag es v{ver} pero VERSION dice {actual}.")
    cl = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notas = notas_de(cl, ver)
    if not notas:
        sys.exit(f"El CHANGELOG no tiene la sección [{ver}].")
    armar_zip(ver, cl)
    (ROOT / "dist" / "notas.md").write_text(notas + "\n", encoding="utf-8")


def esperar_release(repo, ver, timeout=2700):
    """Espera a que el CI publique el release del tag (build + humo tardan ~10-15 min)."""
    url = f"https://api.github.com/repos/{repo}/releases/tags/v{ver}"
    fin = time.time() + timeout
    while time.time() < fin:
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                rel = json.load(r)
            print(f"Release v{ver} publicado: {rel['html_url']} ({len(rel.get('assets', []))} archivos)")
            return True
        except OSError:   # 404 mientras el CI no termina
            print(f"Esperando que el CI de Windows publique v{ver}...")
            time.sleep(60)
    print(f"El release v{ver} no apareció; mirá el CI en https://github.com/{repo}/actions")
    return False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if len(args) != 1 or not re.fullmatch(r"\d+\.\d+\.\d+", args[0]):
        sys.exit("Uso: python tools/release.py X.Y.Z [--dry-run | --ci]")
    ver = args[0]
    if "--ci" in sys.argv:
        return modo_ci(ver)
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
    if not notas_de(cl, "Sin publicar"):
        sys.exit("La sección [Sin publicar] del CHANGELOG está vacía.")
    cl = cl.replace("## [Sin publicar]\n", f"## [Sin publicar]\n\n## [{ver}] - {date.today()}\n", 1)

    if dry:
        armar_zip(ver, cl)
        print("--dry-run: no se tocó el repo ni se publicó nada.")
        return

    # Tabla de armas al día en cada release; si no hay internet se publica la que ya está.
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
    (ROOT / "CHANGELOG.md").write_text(cl, encoding="utf-8")
    (ROOT / "VERSION").write_text(ver + "\n", encoding="utf-8")

    run("git", "add", "VERSION", "CHANGELOG.md", "data/weapon_stats.json", "data/tier_model.json")
    run("git", "commit", "-m", f"Version {ver}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    run("git", "tag", f"v{ver}")
    run("git", "push", "origin", "HEAD", f"v{ver}")
    repo = re.search(r"github\.com[:/](.+?)(?:\.git)?$", run("git", "remote", "get-url", "origin", capture=True)).group(1)
    print(f"Tag v{ver} pusheado: el CI de Windows arma el instalador y publica el release.")
    if not esperar_release(repo, ver):
        sys.exit(1)


if __name__ == "__main__":
    main()
