"""Tests de la calibración por arma (sin red ni base): signo, encogimiento, niveles y
la regla de publicar sólo lo que mejora en datos que no vio.
Uso: python -m unittest discover -s tests"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import calibration
from tools import estimator_job as job


class Factor(unittest.TestCase):
    def test_corrige_el_sesgo_no_lo_duplica(self):
        # El estimado viene 25 % arriba: el factor tiene que bajarlo.
        e = calibration.factor_entry([math.log(1.25)] * 30)
        self.assertLess(e["f"], 1)
        self.assertAlmostEqual(e["f"], math.exp(-math.log(1.25) * 30 / 40), places=3)

    def test_pocas_ventas_se_encogen_hacia_uno(self):
        pocas = calibration.factor_entry([math.log(2)] * 4)
        muchas = calibration.factor_entry([math.log(2)] * 40)
        self.assertGreater(pocas["f"], muchas["f"])   # más cerca de 1 con pocos datos
        self.assertLess(pocas["f"], 1)

    def test_tope(self):
        e = calibration.factor_entry([math.log(50)] * 200)
        self.assertGreaterEqual(e["f"], 1 / calibration.CAP - 1e-9)

    def test_sin_muestras_no_hay_factor(self):
        self.assertIsNone(calibration.factor_entry([]))

    def test_fit_descarta_armas_con_pocas_ventas(self):
        f = calibration.fit({"a": [0.1] * 3, "b": [0.1] * 40})
        self.assertNotIn("a", f)
        self.assertIn("b", f)


class Aplicar(unittest.TestCase):
    def test_multiplica_y_deja_la_razon(self):
        est = {"price": 100, "low": 80, "high": 130, "reasons": []}
        calibration.apply(est, {"por_arma": {"x": {"n": 20, "f": 0.8}}}, "x")
        self.assertEqual((est["price"], est["low"], est["high"]), (80, 64, 104))
        self.assertEqual(est["reasons"][-1]["key"], "calibrado")

    def test_sin_factor_o_correccion_minima_no_toca(self):
        est = {"price": 100, "low": 80, "high": 130}
        calibration.apply(est, {}, "x")
        calibration.apply(est, {"por_arma": {"x": {"n": 9, "f": 1.004}}}, "x")
        self.assertEqual(est["price"], 100)

    def test_no_se_pisan_los_niveles(self):
        factors = {"por_arma": {"x": {"n": 20, "f": 0.8}}, "todo": {"*": {"n": 99, "f": 1.3}}}
        nivel, f = job.lookup(factors, "x", "rifle")
        self.assertEqual((nivel, f["f"]), ("por_arma", 0.8))
        nivel, f = job.lookup(factors, "otra", "rifle")
        self.assertEqual((nivel, f["f"]), ("todo", 1.3))


def casos(arma, n, err, t0=0, rt="rifle"):
    return [(arma, rt, t0 + i, err) for i in range(n)]


class Elegir(unittest.TestCase):
    def test_publica_cuando_el_sesgo_es_estable(self):
        # Un arma que siempre viene 30 % arriba: el factor tiene que publicarse.
        train = casos("a", 60, math.log(1.3))
        test = casos("a", 60, math.log(1.3), t0=1000)
        factors, rep = job.choose(train, test)
        self.assertIn("por_arma", factors)
        self.assertTrue(rep["niveles"]["por_arma"]["publica"])
        self.assertLess(rep["despues"]["med"], rep["antes"]["med"])

    def test_no_publica_si_el_sesgo_cambia_de_signo(self):
        # Entrena arriba y prueba abajo: corregir con el pasado empeoraría.
        train = casos("a", 60, math.log(1.3))
        test = casos("a", 60, math.log(0.7), t0=1000)
        factors, rep = job.choose(train, test)
        self.assertFalse(rep["niveles"]["por_arma"]["publica"])
        self.assertFalse(rep["niveles"]["todo"]["publica"])

    def test_estructura_publicada(self):
        doc = job.publish_shape({"todo": {"*": {"n": 40, "f": 0.9}}}, {"niveles": {"todo": {"publica": True}}})
        self.assertEqual(doc["v"], 1)
        self.assertEqual(doc["factors"]["todo"]["*"]["f"], 0.9)
        self.assertTrue(doc["validated"]["todo"])


class PricingConFactores(unittest.TestCase):
    """El estimado de la app aplica lo que publica la nube, y si el archivo falta no cambia nada."""

    def setUp(self):
        import json
        import tempfile
        import pricing
        self.pricing = pricing
        self.dir = tempfile.mkdtemp()
        self.path = Path(self.dir) / "estimator_factors.json"
        pricing._factors_cache.update(mtime=None, levels={})
        pricing.factors_path_original = pricing.factors_path
        pricing.factors_path = lambda: self.path
        self.mine = {"stats": [{"slug": "critical_chance", "value": 100.0, "positive": True},
                               {"slug": "multishot", "value": 80.0, "positive": True}],
                     "rolls": 5, "rank": 8}
        self.market = [{"id": f"a{i}", "p": 100 + i * 10, "st": "ingame", "r": 5, "k": 8, "nm": f"v{i}",
                        "s": [["critical_chance", 100.0, True], ["multishot", 80.0, True]]} for i in range(8)]
        self.base = pricing.estimate(dict(self.mine), self.market, weapon="x", rtype="rifle")

    def tearDown(self):
        self.pricing.factors_path = self.pricing.factors_path_original
        self.pricing._factors_cache.update(mtime=None, levels={})

    def test_aplica_el_factor_del_arma(self):
        import json
        self.path.write_text(json.dumps({"v": 1, "updated": "2026-10-31T00:00:00Z",
                                         "factors": {"por_arma": {"x": {"n": 40, "f": 0.8}}}}), encoding="utf-8")
        est = self.pricing.estimate(dict(self.mine), self.market, weapon="x", rtype="rifle")
        self.assertEqual(est["price"], round(self.base["price"] * 0.8))
        self.assertEqual(est["reasons"][-1]["key"], "calibrado")

    def test_sin_archivo_queda_igual(self):
        est = self.pricing.estimate(dict(self.mine), self.market, weapon="x", rtype="rifle")
        self.assertEqual(est["price"], self.base["price"])


if __name__ == "__main__":
    unittest.main()
