"""Tests del modelo de precio entrenado con ventas (sin red ni base): evaluación de los
árboles en Python puro, validación del archivo publicado, vencimiento, corrección de sesgo
y cómo lo usa pricing. Si lightgbm está instalado, compara contra sus predicciones.
Uso: python -m unittest discover -s tests"""
import datetime as dt
import gzip
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cloudapi
import price_model as pm
import pricing
from tools import price_model_job as job
from tools.estimator_lambda import handler as lambda_handler


def stamp(days_ago=0):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def leaf(v):
    return [[], [], [], [], [], [], [v]]


def split(feat, thr, lo, hi, default_left=1, missing=0):
    """Árbol de un corte: feature <= thr -> lo, si no hi."""
    return [[feat], [thr], [~0], [~1], [default_left], [missing], [lo, hi]]


def doc(trees=None, bias=None, updated=None, **kw):
    cols = ["+critical_chance", "npos", "rolls", "wenc"]
    base = math.log(100) / pm.MIN_TREES
    d = {"schema": pm.SCHEMA, "features_version": pm.FEATURES_VERSION, "updated": updated or stamp(),
         "features": cols,
         "trees": trees if trees is not None else [split(0, 100.0, base * 0.5, base * 1.5)] * pm.MIN_TREES,
         "enc": {"gmed": 4.0, "types": {"rifle": 4.2}, "weapons": {"Soma": [5.0, 5.5, 3.0]}},
         "bias": bias if bias is not None else []}
    d.update(kw)
    return d


VIEW = {"stats": [{"slug": "critical_chance", "value": 150.0, "positive": True},
                  {"slug": "multishot", "value": 90.0, "positive": True}],
        "rolls": 3, "rank": 8}


class Arboles(unittest.TestCase):
    def test_un_corte(self):
        t = split(0, 10.0, 1.0, 2.0)
        self.assertEqual(pm._tree(t, [5.0]), 1.0)
        self.assertEqual(pm._tree(t, [10.0]), 1.0)
        self.assertEqual(pm._tree(t, [11.0]), 2.0)

    def test_hoja_sola(self):
        self.assertEqual(pm._tree(leaf(0.7), [0.0]), 0.7)

    def test_faltante_como_cero_sigue_default(self):
        # missing=1 (Zero): el 0 va por default_left, aunque el umbral diga otra cosa
        t = split(0, -1.0, 1.0, 2.0, default_left=1, missing=1)
        self.assertEqual(pm._tree(t, [0.0]), 1.0)
        t = split(0, 5.0, 1.0, 2.0, default_left=0, missing=1)
        self.assertEqual(pm._tree(t, [0.0]), 2.0)

    def test_export_desde_dump(self):
        dump = {"tree_info": [{"tree_structure": {
            "split_index": 0, "split_feature": 1, "threshold": 2.5, "decision_type": "<=",
            "default_left": True, "missing_type": "None",
            "left_child": {"leaf_index": 0, "leaf_value": 0.1},
            "right_child": {"split_index": 1, "split_feature": 0, "threshold": 7.0, "decision_type": "<=",
                            "default_left": False, "missing_type": "Zero",
                            "left_child": {"leaf_index": 1, "leaf_value": 0.2},
                            "right_child": {"leaf_index": 2, "leaf_value": 0.3}}}},
            {"tree_structure": {"leaf_value": 0.05}}]}
        trees = pm.export_trees(dump)
        self.assertTrue(all(pm._check_tree(t, 2) for t in trees))
        self.assertEqual(pm._tree(trees[0], [0.0, 1.0]), 0.1)
        self.assertEqual(pm._tree(trees[0], [3.0, 5.0]), 0.2)
        self.assertEqual(pm._tree(trees[0], [9.0, 5.0]), 0.3)
        self.assertEqual(pm._tree(trees[1], [9.0, 5.0]), 0.05)

    def test_export_rechaza_cortes_categoricos(self):
        dump = {"tree_info": [{"tree_structure": {
            "split_index": 0, "split_feature": 0, "threshold": "1||2", "decision_type": "==",
            "default_left": True, "missing_type": "None",
            "left_child": {"leaf_index": 0, "leaf_value": 0.1},
            "right_child": {"leaf_index": 1, "leaf_value": 0.2}}}]}
        with self.assertRaises(ValueError):
            pm.export_trees(dump)


class Validacion(unittest.TestCase):
    def test_valido(self):
        m = pm.check(doc())
        self.assertIsNotNone(m)
        self.assertEqual(m["ix"]["wenc"], 3)

    def test_rechazos(self):
        malos = [
            doc(schema=pm.SCHEMA + 1),
            doc(features_version=pm.FEATURES_VERSION + 1),
            doc(updated="ayer"),
            doc(features=[]),
            doc(features=["a", "a", "b", "c"]),
            doc(trees=[split(0, 1.0, 0.1, 0.2)] * (pm.MIN_TREES - 1)),
            doc(trees=[split(9, 1.0, 0.1, 0.2)] * pm.MIN_TREES),          # feature inexistente
            doc(trees=[[[0], [1.0], [0], [~1], [1], [0], [0.1, 0.2]]] * pm.MIN_TREES),   # ciclo
            doc(trees=[split(0, float("nan"), 0.1, 0.2)] * pm.MIN_TREES),
            doc(trees=[split(0, 1.0, 0.1, 0.2, missing=7)] * pm.MIN_TREES),
            doc(enc={"gmed": "x", "types": {}, "weapons": {}}),
            doc(enc={"gmed": 4.0, "types": {}, "weapons": {"Soma": [1, 2]}}),
            doc(bias=[[1.0, 5.0]]),                                          # corrección absurda
            doc(bias=[[1.0]]),
        ]
        for d in malos:
            self.assertIsNone(pm.check(d), d)
        self.assertIsNone(pm.check({"schema": pm.SCHEMA}))
        self.assertIsNone(pm.check([]))

    def test_vencimiento(self):
        now = dt.datetime(2026, 11, 20)
        self.assertTrue(pm.fresh(now - dt.timedelta(days=pm.MAX_AGE_DAYS - 1), now))
        self.assertFalse(pm.fresh(now - dt.timedelta(days=pm.MAX_AGE_DAYS + 1), now))


class Archivo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name) / "price_model.json"
        self._old = pm._path_override
        pm.set_path(self.p)
        pm._cache.update(mtime=None, checked=0.0, model=None)
        self.hook = mock.Mock()
        pm.set_refresh_hook(self.hook)

    def tearDown(self):
        pm._path_override = self._old
        pm.set_refresh_hook(None)
        pm._cache.update(mtime=None, checked=0.0, model=None)
        self.tmp.cleanup()

    def test_sin_archivo_pide_bajarlo(self):
        self.assertIsNone(pm.current())
        self.hook.assert_called_once()

    def test_archivo_vigente(self):
        self.p.write_text(json.dumps(doc()), encoding="utf-8")
        self.assertIsNotNone(pm.current())
        self.hook.assert_not_called()

    def test_vencido_no_se_usa(self):
        self.p.write_text(json.dumps(doc(updated=stamp(pm.MAX_AGE_DAYS + 1))), encoding="utf-8")
        self.assertIsNone(pm.current())

    def test_roto_no_se_usa(self):
        self.p.write_text("{no es json", encoding="utf-8")
        self.assertIsNone(pm.current())

    def test_hook_que_falla_no_rompe(self):
        self.hook.side_effect = RuntimeError("sin red")
        self.assertIsNone(pm.current())


class Prediccion(unittest.TestCase):
    def test_predice_por_el_corte(self):
        m = pm.check(doc())
        d = pm.features("Soma", "rifle", [("critical_chance", 150.0, True)], 3, 8, m["enc"])
        self.assertGreater(d["+critical_chance"], 100)
        self.assertAlmostEqual(math.exp(pm.predict_log(m, d)), 100 ** 1.5, delta=1)
        d["+critical_chance"] = 50
        self.assertAlmostEqual(math.exp(pm.predict_log(m, d)), 10, delta=0.01)

    def test_codificacion_del_arma(self):
        enc = doc()["enc"]
        st = [("critical_chance", 100.0, True)]
        self.assertEqual(pm.features("Soma", "rifle", st, 0, 0, enc)["wenc"], 5.0)
        self.assertEqual(pm.features("Otra", "rifle", st, 0, 0, enc)["wenc"], 4.2)   # por tipo
        self.assertEqual(pm.features("Otra", "melee", st, 0, 0, enc)["wenc"], 4.0)   # general
        self.assertEqual(pm.features("Otra", "rifle", st, 0, 0, enc)["wn"], 0.0)

    def test_negativo_y_rank(self):
        enc = doc()["enc"]
        st = [("critical_chance", 100.0, True), ("zoom", -30.0, False)]
        d0 = pm.features("Soma", "rifle", st, 0, 0, enc)
        d8 = pm.features("Soma", "rifle", st, 0, 8, enc)
        self.assertEqual((d0["hasneg"], d0["npos"], d0["rank8"], d8["rank8"]), (1, 1, 0, 1))
        self.assertGreater(d0["-zoom"], 0)
        self.assertAlmostEqual(d8["+critical_chance"], 100.0 / pricing._config_bonus(1, True), places=6)

    def test_sesgo_por_tramo(self):
        bias = [[math.log(30), 0.2], [math.log(120), 0.0], [None, -0.1]]
        self.assertEqual(pm.bias_for(bias, math.log(10)), 0.2)
        self.assertEqual(pm.bias_for(bias, math.log(60)), 0.0)
        self.assertEqual(pm.bias_for(bias, math.log(900)), -0.1)
        self.assertEqual(pm.bias_for([], 3.0), 0.0)
        m = pm.check(doc(bias=bias))
        d = {"+critical_chance": 50.0}
        self.assertAlmostEqual(math.exp(pm.predict_log(m, d)), 10 * math.exp(0.2), delta=0.01)

    def test_sin_positivos_o_sin_arma_no_predice(self):
        m = pm.check(doc())
        self.assertIsNone(pm.predict("Soma", "rifle", {"stats": [{"slug": "zoom", "value": -5, "positive": False}]}, m))
        self.assertIsNone(pm.predict(None, "rifle", VIEW, m))
        self.assertGreater(pm.predict("Soma", "rifle", VIEW, m), 1)


class EnPricing(unittest.TestCase):
    def test_reemplaza_el_precio_y_lo_explica(self):
        est = {"price": 200, "low": 150, "high": 260, "reasons": [], "adj": 1.1}
        with mock.patch.object(pm, "predict", return_value=100):
            pricing._apply_model(est, dict(VIEW), "Soma", "rifle", [])
        self.assertEqual((est["price"], est["source"], est["listings_price"]), (100, "model", 200))
        self.assertEqual(est["reasons"][0], {"key": "salesModel", "p": 200})
        self.assertLessEqual(est["low"], 100)
        self.assertGreaterEqual(est["high"], 100)

    def test_sin_modelo_queda_el_de_publicaciones(self):
        est = {"price": 200, "low": 150, "high": 260, "reasons": [{"key": "x"}]}
        before = dict(est)
        with mock.patch.object(pm, "predict", return_value=None):
            pricing._apply_model(est, dict(VIEW), "Soma", "rifle", [])
        self.assertEqual(est, before)
        with mock.patch.object(pm, "predict", side_effect=RuntimeError("boom")):
            pricing._apply_model(est, dict(VIEW), "Soma", "rifle", [])
        self.assertEqual(est, before)

    def test_respeta_el_techo_de_comparables_baratos(self):
        est = {"price": 50, "low": 40, "high": 60, "reasons": []}
        with mock.patch.object(pm, "predict", return_value=1000):
            pricing._apply_model(est, dict(VIEW), "Soma", "rifle", [20, 20, 20])
        self.assertEqual(est["price"], 50)
        self.assertIn({"key": "cheaperCap", "n": 3}, est["reasons"])


class Job(unittest.TestCase):
    def test_sesgo_solo_con_ventas_suficientes(self):
        preds = [math.log(20)] * job.BIAS_MIN_N
        ys = [p + 0.3 for p in preds]
        b = job.fit_bias(preds, ys)
        self.assertGreater(b[0][1], 0)
        self.assertLessEqual(b[0][1], job.BIAS_MAX)
        self.assertTrue(all(c == 0 for _, c in b[1:]))
        self.assertIsNotNone(pm.check(doc(bias=b)))
        self.assertEqual(job.fit_bias(preds[:job.BIAS_MIN_N - 1], ys[:job.BIAS_MIN_N - 1]), [])


class Nube(unittest.TestCase):
    def test_publica_comprimido(self):
        s3 = mock.Mock()
        with mock.patch.dict("os.environ", {"ESTIMATOR_BUCKET": "b"}), \
                mock.patch.dict(sys.modules, {"boto3": mock.Mock(client=mock.Mock(return_value=s3))}):
            lambda_handler.publish(doc(), lambda_handler.PRICE_MODEL_KEY, gz=True)
        kw = s3.put_object.call_args.kwargs
        self.assertEqual((kw["Key"], kw["ContentEncoding"]), ("price_model.json", "gzip"))
        self.assertIsNotNone(pm.check(json.loads(gzip.decompress(kw["Body"]))))

    def test_handler_falla_a_la_vista_si_no_publica(self):
        with mock.patch.object(lambda_handler, "run_price_model",
                               return_value={"ok": False, "motivo": "no mejora"}):
            with self.assertRaises(RuntimeError):
                lambda_handler.handler_modelo({}, None)

    def test_la_app_no_guarda_un_modelo_invalido(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old = pm._path_override
        self.addCleanup(lambda: setattr(pm, "_path_override", old))
        pm.set_path(Path(tmp.name) / "price_model.json")
        api = object.__new__(cloudapi.CloudMixin)
        for d, ok in ((doc(schema=99), False), (doc(), True)):
            r = mock.Mock(json=mock.Mock(return_value=d))
            with mock.patch.object(cloudapi.requests, "get", return_value=r):
                api._price_model_download()
            self.assertEqual(pm.path().exists(), ok)


try:
    import lightgbm
    import numpy as np
except ImportError:   # en la app y en el CI no está: el job de la nube sí lo tiene
    lightgbm = None


@unittest.skipUnless(lightgbm, "lightgbm no instalado")
class ContraLightgbm(unittest.TestCase):
    def test_python_puro_igual_que_lightgbm(self):
        rng = np.random.default_rng(1)
        X = rng.normal(size=(3000, 6))
        X[rng.random(X.shape) < 0.3] = 0.0     # muchos ceros, como las stats que faltan
        y = X[:, 0] * 2 + np.sin(X[:, 1]) + (X[:, 2] > 0) * 0.5 + rng.normal(scale=0.1, size=3000)
        b = lightgbm.train(dict(job.PARAMS, verbose=-1), lightgbm.Dataset(X, y), 80)
        trees = pm.export_trees(b.dump_model())
        self.assertTrue(all(pm._check_tree(t, 6) for t in trees))
        model = {"ix": {str(i): i for i in range(6)}, "trees": trees, "bias": []}
        ref = b.predict(X[:500])
        for row, r in zip(X[:500], ref):
            got = pm.predict_log(model, {str(i): v for i, v in enumerate(row)})
            self.assertAlmostEqual(got, r, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
