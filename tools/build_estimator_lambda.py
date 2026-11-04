"""Arma y (si se pide) despliega las Lambdas del estimador y de los datos de armas.

Copia la lógica tal cual está en el repo -- sin duplicar archivos -- junto con
pymongo, numpy, lightgbm y los datos que usa pricing, arma el zip y lo sube con CloudFormation.
Las tres funciones comparten el zip y cambian sólo el handler.

  python tools/build_estimator_lambda.py            # sólo arma dist/estimator.zip
  python tools/build_estimator_lambda.py --deploy    # sube el zip y actualiza el stack
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "estimator"
ZIP = ROOT / "dist" / "estimator.zip"
FILES = {"pricing.py": "", "calibration.py": "", "estimator_mongo.py": "", "estimator_job.py": "tools",
         "weapon_data_job.py": "tools", "train_tier.py": "tools", "build_weapon_data.py": "tools",
         "price_model.py": "", "price_model_job.py": "tools"}
# Lambda descomprime el código en 250 MB como mucho.
MAX_UNZIPPED = 250 * 1024 * 1024
BUCKET = "riven-stock-estimator-099572291636"
STACK = "riven-stock-estimator"
PROFILE = "cuenta_personal"
REGION = "us-east-1"
PASOS = 4


def progress(n):
    print(f"PROGRESS {n}/{PASOS}", flush=True)


def build(python=None):
    python = python or sys.executable
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for f, sub in FILES.items():
        shutil.copy2(ROOT / sub / f if sub else ROOT / f, OUT / f)
    shutil.copy2(ROOT / "tools" / "estimator_lambda" / "handler.py", OUT / "handler.py")
    (OUT / "data").mkdir()
    for f in ("weapon_stats.json", "tier_model.json"):
        shutil.copy2(ROOT / "data" / f, OUT / "data" / f)
    # Wheels de Linux para el runtime de Lambda (numpy es binario: el de esta PC puede no servir).
    subprocess.run([python, "-m", "pip", "install", "-q", "--target", str(OUT), "--upgrade",
                    "--no-compile", "--platform", "manylinux2014_x86_64", "--only-binary=:all:",
                    "--python-version", "3.12", "--implementation", "cp",
                    "pymongo", "dnspython", "numpy", "scipy", "lightgbm"], check=True)
    _libgomp(python)
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    if size > MAX_UNZIPPED:
        raise SystemExit(f"el código descomprimido pesa {size // 2**20} MB, más que el límite de Lambda")
    ZIP.parent.mkdir(exist_ok=True)
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(OUT))
    print(f"{ZIP} ({ZIP.stat().st_size // 1024} KB, {len(zipfile.ZipFile(ZIP).namelist())} archivos)")
    return ZIP


def _libgomp(python):
    """lib_lightgbm.so necesita libgomp.so.1, que no viene en el runtime de Lambda ni en su
    rueda. Se toma la que trae la rueda manylinux de scikit-learn y queda en lib/, que
    Lambda pone en LD_LIBRARY_PATH."""
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([python, "-m", "pip", "download", "-q", "--no-deps", "--dest", d,
                        "--platform", "manylinux_2_28_x86_64", "--only-binary=:all:",
                        "--python-version", "3.12", "--implementation", "cp", "scikit-learn"], check=True)
        whl = next(Path(d).glob("scikit_learn-*.whl"))
        with zipfile.ZipFile(whl) as z:
            name = next(n for n in z.namelist() if "/libgomp" in n)
            (OUT / "lib").mkdir(exist_ok=True)
            (OUT / "lib" / "libgomp.so.1").write_bytes(z.read(name))


def deploy(uri):
    # Clave con el hash del zip: si se sube siempre al mismo lugar, CloudFormation
    # no ve cambios en el template y deja la versión vieja del código.
    key = f"estimator-{hashlib.sha256(ZIP.read_bytes()).hexdigest()[:10]}.zip"
    subprocess.run(["aws", "s3", "mb", f"s3://{BUCKET}", "--region", REGION, "--profile", PROFILE],
                   capture_output=True)   # si ya existe, sigue
    subprocess.run(["aws", "s3", "cp", str(ZIP), f"s3://{BUCKET}/{key}",
                    "--profile", PROFILE, "--region", REGION], check=True)
    progress(2)
    # Los parámetros van por archivo: en la línea de comandos la clave de Mongo se vería
    # en la lista de procesos. mkstemp lo crea legible sólo por el dueño.
    fd, params = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump([f"MongoUri={uri}", f"CodeBucket={BUCKET}", f"CodeKey={key}"], f)
        subprocess.run(["aws", "cloudformation", "deploy", "--template-file", str(ROOT / "cloud" / "estimator.yml"),
                        "--stack-name", STACK, "--capabilities", "CAPABILITY_NAMED_IAM",
                        "--parameter-overrides", f"file://{params}",
                        "--profile", PROFILE, "--region", REGION], check=True)
    finally:
        os.unlink(params)
    progress(3)
    out = subprocess.run(["aws", "cloudformation", "describe-stacks", "--stack-name", STACK,
                          "--profile", PROFILE, "--region", REGION,
                          "--query", "Stacks[0].Outputs", "--output", "json"],
                         capture_output=True, text=True, check=True)
    print(out.stdout)
    progress(4)


def mongo_uri():
    for line in (ROOT / "cloud" / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("MONGODB_URI="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("Falta MONGODB_URI en cloud/.env")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    a = ap.parse_args()
    progress(0)
    build()
    progress(1)
    if a.deploy:
        deploy(mongo_uri())
