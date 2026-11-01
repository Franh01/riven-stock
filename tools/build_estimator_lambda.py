"""Arma y (si se pide) despliega la Lambda del estimador.

Copia la lógica tal cual está en el repo -- sin duplicar archivos -- junto con
pymongo y los datos que usa pricing, arma el zip y lo sube con CloudFormation.

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
FILES = {"pricing.py": "", "calibration.py": "", "estimator_mongo.py": "", "estimator_job.py": "tools"}
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
    shutil.copy2(ROOT / "data" / "weapon_stats.json", OUT / "data" / "weapon_stats.json")
    subprocess.run([python, "-m", "pip", "install", "-q", "--target", str(OUT), "--upgrade",
                    "--no-compile", "pymongo", "dnspython"], check=True)
    ZIP.parent.mkdir(exist_ok=True)
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(OUT))
    print(f"{ZIP} ({ZIP.stat().st_size // 1024} KB, {len(zipfile.ZipFile(ZIP).namelist())} archivos)")
    return ZIP


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
