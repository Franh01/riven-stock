"""Lambda del estimador (riven-stock): ajusta la calibración y la publica.

Dos formas de llamarla:
- Programada (EventBridge, una vez por día): mide el error contra las ventas
  reales, ajusta los factores, se autovalida y publica sólo lo que mejora.
- Por HTTP (Function URL, la usa la app): devuelve los factores publicados.

Los archivos de lógica (pricing.py, calibration.py, estimator_job.py,
estimator_mongo.py y data/weapon_stats.json) los copia el script de build:
acá no se duplica nada.
"""
import json
import os

ESTIMATOR_COL = "estimator"


def _json(status, body, cache="public, max-age=300"):
    return {"statusCode": status,
            "headers": {"Content-Type": "application/json", "Cache-Control": cache,
                        "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(body, ensure_ascii=False)}


def serve():
    """GET: los factores publicados (lo que la app baja una vez por día)."""
    import estimator_mongo
    from pymongo import MongoClient
    client = MongoClient(estimator_mongo.uri(), serverSelectionTimeoutMS=8000)
    doc = client.get_default_database()[ESTIMATOR_COL].find_one({"_id": "factors"}) or {}
    doc.pop("_id", None)
    return _json(200, doc or {"v": 1, "factors": {}})


def run_job():
    """El proceso nocturno. Devuelve un resumen (queda en el log de la Lambda)."""
    import datetime as dt
    import estimator_job
    import estimator_mongo

    cases = estimator_mongo.cases_from_mongo()
    if len(cases) < 50:
        return {"ok": False, "error": f"muy pocas ventas con mercado: {len(cases)}"}
    train, test = estimator_job.split(cases)
    factors, report = estimator_job.choose(train, test)
    doc = estimator_job.publish_shape(factors, report)
    estimator_mongo.save(doc, estimator_mongo.fetch_rtypes())
    resumen = {lvl: {"factores": len(factors.get(lvl) or {}), "validado": doc["validated"].get(lvl)}
               for lvl in estimator_job.LEVELS}
    return {"ok": True, "casos": len(cases), "entrenamiento": len(train), "prueba": len(test),
            "niveles": resumen, "med_antes": round(report["antes"]["med"], 4),
            "med_despues": round(report["despues"]["med"], 4),
            "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def handler(event, context):
    if (event or {}).get("requestContext", {}).get("http"):
        try:
            return serve()
        except Exception as e:  # noqa: BLE001 -- la app se queda con lo que ya tiene
            return _json(503, {"error": f"estimador no disponible: {e.__class__.__name__}"}, "no-store")
    if os.environ.get("ESTIMATOR_SERVE_ONLY") == "1":
        return {"ok": True, "skipped": "serve-only"}
    try:
        return run_job()
    except Exception as e:  # noqa: BLE001 -- el evento de Lambda lo muestra
        print(f"ERROR: {e!r}")
        raise
