"""Lambda del estimador (riven-stock): ajusta la calibración y la publica.

Corre una vez por día (EventBridge): mide el error contra las ventas reales,
ajusta los factores, se autovalida y deja en S3 sólo lo que mejora. La app baja
ese archivo público; la función no tiene URL ni atiende pedidos de nadie.

Los archivos de lógica (pricing.py, calibration.py, estimator_job.py,
estimator_mongo.py y data/weapon_stats.json) los copia el script de build:
acá no se duplica nada. boto3 ya viene en el runtime de Lambda.
"""
import datetime as dt
import json
import os

FACTORS_KEY = "factors.json"


def publish(doc):
    """Deja los factores en el bucket público, que es lo único que ve la app."""
    import boto3
    boto3.client("s3").put_object(Bucket=os.environ["ESTIMATOR_BUCKET"], Key=FACTORS_KEY,
                                  Body=json.dumps(doc, ensure_ascii=False).encode("utf-8"),
                                  ContentType="application/json", CacheControl="public, max-age=3600")


def _stats(s):
    return {k: round(v, 4) for k, v in s.items()}


def run_job():
    """El proceso nocturno. Devuelve un resumen (handler lo deja en el log)."""
    import estimator_job
    import estimator_mongo

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


def handler(event, context):
    try:
        resumen = run_job()
    except Exception as e:  # noqa: BLE001 -- el evento de Lambda lo muestra
        print(f"ERROR: {e!r}")
        raise
    print(json.dumps(resumen, ensure_ascii=False))
    return resumen
