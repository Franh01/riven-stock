"""Lambdas del estimador (riven-stock): calibración (handler) y datos de armas (handler_armas).

Corre una vez por día (EventBridge): mide el error contra las ventas reales,
ajusta los factores, se autovalida y deja en S3 sólo lo que mejora. La app baja
ese archivo público; la función no tiene URL ni atiende pedidos de nadie.

handler_armas regenera los datos de armas y el modelo caro/barato
(tools/weapon_data_job.py) media hora antes, y la calibración mide con esos mismos datos.
handler_modelo (2026-11-04) entrena el modelo de precio con las ventas (tools/price_model_job.py)
y publica price_model.json solo si pasa su compuerta; lightgbm y numpy viajan en el zip.

Los archivos de lógica (pricing.py, calibration.py, estimator_job.py, weapon_data_job.py,
estimator_mongo.py, data/*.json...) los copia el script de build: acá no se duplica
nada. boto3 ya viene en el runtime de Lambda.
"""
import datetime as dt
import json
import os

import urllib.request

FACTORS_KEY = "factors.json"
WEAPON_DATA_KEY = "weapon_data.json"
PRICE_MODEL_KEY = "price_model.json"


def publish(doc, key=FACTORS_KEY, gz=False):
    """Deja el documento en el bucket público, que es lo único que ve la app. El modelo
    de precio va comprimido (son varios MB de árboles); requests lo descomprime solo."""
    import boto3
    body = json.dumps(doc, ensure_ascii=False, separators=(",", ":") if gz else None).encode("utf-8")
    extra = {}
    if gz:
        import gzip
        body, extra = gzip.compress(body, 9), {"ContentEncoding": "gzip"}
    boto3.client("s3").put_object(Bucket=os.environ["ESTIMATOR_BUCKET"], Key=key, Body=body,
                                  ContentType="application/json", CacheControl="public, max-age=3600", **extra)


def _stats(s):
    return {k: round(v, 4) for k, v in s.items()}


def run_job():
    """El proceso nocturno. Devuelve un resumen (handler lo deja en el log)."""
    import estimator_job
    import estimator_mongo

    _use_published_weapon_data()
    client = estimator_mongo.db_client()
    try:
        cases = estimator_mongo.cases_from_mongo(client=client)
        if len(cases) < 50:
            return {"ok": False, "error": f"muy pocas ventas con mercado: {len(cases)}"}
        train, test = estimator_job.split(cases)
        factors, report = estimator_job.choose(train, test)
        doc = estimator_job.publish_shape(factors, report)
        estimator_mongo.save(doc, estimator_mongo.fetch_rtypes(), client=client)
        publish(doc)
    finally:
        client.close()
    resumen = {lvl: {"factores": len(factors.get(lvl) or {}), "validado": doc["validated"].get(lvl)}
               for lvl in estimator_job.LEVELS}
    return {"ok": True, "casos": len(cases), "entrenamiento": len(train), "prueba": len(test),
            "niveles": resumen, "antes": _stats(report["antes"]), "despues": _stats(report["despues"]),
            "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def _use_published_weapon_data(path="/tmp/weapon_data.json"):
    """La calibración mide con los mismos datos de armas que usa la app; si no se pueden
    bajar, quedan los del zip."""
    import pricing
    try:
        with urllib.request.urlopen(pricing.WEAPON_DATA_URL, timeout=30) as r:
            body = r.read()
        if pricing.check_weapon_data(json.loads(body)):
            with open(path, "wb") as f:
                f.write(body)
            pricing.set_weapon_data_path(path)
    except (OSError, ValueError) as e:
        print(f"weapon_data.json: {e!r}")


def run_weapon_data():
    import estimator_mongo
    import weapon_data_job

    client = estimator_mongo.db_client()
    try:
        doc, report = weapon_data_job.run(client)
    finally:
        client.close()
    if doc:
        publish(doc, WEAPON_DATA_KEY)
    return {"ok": doc is not None, "publicado": doc is not None, **report,
            "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def handler_armas(event, context):
    resumen = run_weapon_data()
    print(json.dumps(resumen, ensure_ascii=False))
    if not resumen["ok"]:
        raise RuntimeError("weapon_data.json no se publicó: ninguna parte pasó la compuerta")
    return resumen


def run_price_model():
    import estimator_mongo
    import price_model_job

    _use_published_weapon_data()
    client = estimator_mongo.db_client()
    try:
        doc, report = price_model_job.run(client)
    finally:
        client.close()
    if doc:
        publish(doc, PRICE_MODEL_KEY, gz=True)
    return {"ok": doc is not None, "publicado": doc is not None, **report,
            "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def handler_modelo(event, context):
    resumen = run_price_model()
    print(json.dumps(resumen, ensure_ascii=False, default=str))
    if not resumen["ok"]:
        # Falla a la vista (alarma/log) pero la app sigue con el modelo anterior hasta que venza.
        raise RuntimeError("price_model.json no se publicó: " + str(resumen.get("motivo") or "no pasó la compuerta"))
    return resumen


def handler(event, context):
    try:
        resumen = run_job()
    except Exception as e:  # noqa: BLE001 -- el evento de Lambda lo muestra
        print(f"ERROR: {e!r}")
        raise
    print(json.dumps(resumen, ensure_ascii=False))
    return resumen
