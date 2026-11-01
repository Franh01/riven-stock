"""Tests de la calibración por arma (sin red ni base): signo, encogimiento, niveles y
la regla de publicar sólo lo que mejora en datos que no vio.
Uso: python -m unittest discover -s tests"""
import ast
import datetime as dt
import json
import math
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import calibration
import cloudapi
import pricing
from tools import check_js, release
from tools import estimator_job as job
from tools.estimator_lambda import handler as lambda_handler


def stamp(days_ago=0):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


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


    def test_entrada_rota_cae_al_nivel_siguiente(self):
        for roto in ({"f": "abc", "n": 20}, {"f": None, "n": 20}, {"n": 20}, {"f": float("nan"), "n": 20},
                     {"f": float("inf"), "n": 20}, {"f": 0, "n": 20}, {"f": -2, "n": 20}, {"f": 0.8, "n": "<img>"}, "x"):
            levels = {"por_arma": {"x": roto}, "todo": {"*": {"n": 30, "f": 0.9}}}
            est = calibration.apply({"price": 100, "low": 80, "high": 120}, levels, "x")
            self.assertEqual(est["price"], 90, roto)

    def test_niveles_con_forma_rara_no_rompen(self):
        for levels in ("x", ["x"], {"por_arma": "x"}, {"todo": ["x"]}):
            est = calibration.apply({"price": 100}, levels, "x")
            self.assertEqual(est, {"price": 100})

    def test_factor_fuera_de_rango_se_recorta(self):
        est = calibration.apply({"price": 100}, {"todo": {"*": {"n": 30, "f": 50}}}, "x")
        self.assertEqual(est["price"], round(100 * calibration.CAP))


class Vigencia(unittest.TestCase):
    def test_fecha(self):
        self.assertTrue(calibration.fresh(stamp()))
        self.assertTrue(calibration.fresh(stamp(calibration.MAX_AGE_DAYS - 1)))
        self.assertFalse(calibration.fresh(stamp(calibration.MAX_AGE_DAYS + 1)))

    def test_sin_fecha_valida_no_rige(self):
        for updated in (None, "", "ayer", 7):
            self.assertFalse(calibration.fresh(updated), updated)


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


    def test_publica_lo_aprobado_con_todas_las_ventas(self):
        train = [("a", "rifle", i, math.log(1.25)) for i in range(40)]
        test = [("a", "rifle", 100 + i, math.log(1.5)) for i in range(40)]
        factors, report = job.choose(train, test)
        self.assertTrue(factors["por_arma"])
        self.assertEqual(factors["por_arma"]["a"]["n"], 80)     # lo publicado usa las 80
        self.assertEqual(report["niveles"]["por_arma"]["fitted"], 1)
        fijo = job.fit_levels(train)["por_arma"]["a"]["f"]
        self.assertAlmostEqual(report["niveles"]["por_arma"]["test"]["bias"],
                               job.evaluate(test, {"por_arma": {"a": {"n": 40, "f": fijo}}})[0]["bias"])

    def test_lleva_la_huella_del_pricing_medido(self):
        doc = job.publish_shape({}, {})
        self.assertEqual(doc["pricing_sha"], calibration.code_sha(Path(pricing.__file__)))


class Huella(unittest.TestCase):
    def test_no_dependen_de_los_finales_de_linea(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a", Path(d) / "b"
            a.write_bytes(b"x = 1\ny = 2\n")
            b.write_bytes(b"x = 1\r\ny = 2\r\n")
            self.assertEqual(calibration.code_sha(a), calibration.code_sha(b))

    def test_release_frena_si_la_nube_midio_otro_codigo(self):
        self.assertIsNone(release.estimador_desfasado({"pricing_sha": "abc"}, "abc"))
        self.assertIn("otro pricing.py", release.estimador_desfasado({"pricing_sha": "viejo"}, "abc"))
        self.assertIn("otro pricing.py", release.estimador_desfasado({}, "abc"))
        self.assertIn("No se pudo leer", release.estimador_desfasado(None, "abc"))


class Empaquetado(unittest.TestCase):
    def test_todo_modulo_propio_entra_en_el_release(self):
        # Un .py suelto en la raíz que falte en INCLUIR hace que el zip no arranque.
        root = release.ROOT
        faltan = set()
        for name in release.INCLUIR:
            if not name.endswith(".py"):
                continue
            for n in ast.walk(ast.parse((root / name).read_text(encoding="utf-8"))):
                mods = [a.name for a in n.names] if isinstance(n, ast.Import) else \
                       [n.module] if isinstance(n, ast.ImportFrom) and n.module else []
                faltan |= {f"{m}.py" for m in mods if (root / f"{m}.py").exists()}
        self.assertEqual(faltan - set(release.INCLUIR), set())


class TextosDeLaInterfaz(unittest.TestCase):
    def test_encuentra_las_razones_del_backend(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.py").write_text('est["reasons"].append({"key": "nueva", "n": 1})\n', encoding="utf-8")
            self.assertEqual(check_js.razones_backend(d), {"nueva"})

    def test_cada_razon_del_estimado_tiene_texto(self):
        self.assertIn("calibrado", check_js.razones_backend())
        self.assertEqual(check_js.claves_idioma(), [])

    def test_avisa_si_falta_el_texto_de_una_razon(self):
        with mock.patch.object(check_js, "razones_backend", return_value={"inventada"}):
            self.assertIn("Razón del backend sin texto: why.inventada", check_js.claves_idioma())

    def test_avisa_si_se_queda_ciego(self):
        with mock.patch.object(check_js, "razones_backend", return_value=set()):
            self.assertTrue(any("ciego" in e for e in check_js.claves_idioma()))


class BajarFactores(unittest.TestCase):
    def setUp(self):
        self.app = cloudapi.CloudMixin()
        self.llamadas = []
        self.app._estimator_download = lambda: self.llamadas.append(1)

    def test_muchos_estimados_juntos_bajan_una_sola_vez(self):
        hilos = [threading.Thread(target=self.app.estimator_refresh) for _ in range(50)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        for h in threading.enumerate():
            if h is not threading.current_thread() and h.daemon:
                h.join(1)
        self.assertEqual(len(self.llamadas), 1)

    def test_si_fallo_no_reintenta_hasta_la_hora(self):
        with mock.patch.object(cloudapi.time, "time", return_value=10_000.0):
            self.app.estimator_refresh()
            self.app.estimator_refresh()
        with mock.patch.object(cloudapi.time, "time", return_value=10_000.0 + self.app.ESTIMATOR_RETRY_S):
            self.app.estimator_refresh()
        for h in threading.enumerate():
            if h is not threading.current_thread() and h.daemon:
                h.join(1)
        self.assertEqual(len(self.llamadas), 2)

    def test_respuesta_rara_no_pisa_lo_que_hay(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "f.json"
            path.write_text("previo", encoding="utf-8")
            for cuerpo in ([1, 2], {"factors": {}}, {"updated": "x"}, {"factors": [], "updated": "x"}):
                r = mock.Mock(json=lambda c=cuerpo: c, raise_for_status=lambda: None)
                with mock.patch.object(cloudapi.requests, "get", return_value=r), \
                     mock.patch.object(pricing, "factors_path", return_value=path):
                    cloudapi.CloudMixin()._estimator_download()
                self.assertEqual(path.read_text(encoding="utf-8"), "previo", cuerpo)


class Lambda(unittest.TestCase):
    def setUp(self):
        # En la Lambda los módulos van sueltos en el zip, no bajo tools/.
        parche = mock.patch.dict(sys.modules, {"estimator_job": job})
        parche.start()
        self.addCleanup(parche.stop)

    def test_sin_url_ni_rama_http(self):
        self.assertFalse(hasattr(lambda_handler, "serve"))
        with mock.patch.object(lambda_handler, "run_job", return_value={"ok": False}) as run:
            lambda_handler.handler({"requestContext": {"http": {"method": "GET"}}}, None)
        run.assert_called_once()

    def test_publica_y_cierra_la_conexion(self):
        client = mock.MagicMock()
        cases = [("a", "rifle", i, math.log(1.25)) for i in range(200)]
        with mock.patch("estimator_mongo.db_client", return_value=client), \
             mock.patch("estimator_mongo.cases_from_mongo", return_value=cases), \
             mock.patch("estimator_mongo.fetch_rtypes", return_value={}), \
             mock.patch("estimator_mongo.save") as save, \
             mock.patch.object(lambda_handler, "publish") as pub:
            out = lambda_handler.run_job()
        self.assertTrue(out["ok"])
        self.assertIn("ok", out["antes"])
        pub.assert_called_once()
        self.assertIs(save.call_args.kwargs["client"], client)
        client.close.assert_called_once()

    def test_si_falla_cierra_igual(self):
        client = mock.MagicMock()
        with mock.patch("estimator_mongo.db_client", return_value=client), \
             mock.patch("estimator_mongo.cases_from_mongo", side_effect=RuntimeError("x")):
            with self.assertRaises(RuntimeError):
                lambda_handler.run_job()
        client.close.assert_called_once()


class PricingConFactores(unittest.TestCase):
    """El estimado de la app aplica lo que publica la nube, y si el archivo falta no cambia nada."""

    def setUp(self):
        self.pricing = pricing
        self.dir = tempfile.mkdtemp()
        self.path = Path(self.dir) / "estimator_factors.json"
        pricing._factors_cache.update(mtime=None, levels={}, updated=None)
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
        self.pricing._factors_cache.update(mtime=None, levels={}, updated=None)

    def write(self, updated, f=0.8):
        self.path.write_text(json.dumps({"v": 1, "updated": updated,
                                         "factors": {"por_arma": {"x": {"n": 40, "f": f}}}}), encoding="utf-8")

    def test_aplica_el_factor_del_arma(self):
        self.write(stamp())
        est = self.pricing.estimate(dict(self.mine), self.market, weapon="x", rtype="rifle")
        self.assertEqual(est["price"], round(self.base["price"] * 0.8))
        self.assertEqual(est["reasons"][-1]["key"], "calibrado")

    def test_factores_vencidos_no_se_aplican(self):
        self.write(stamp(calibration.MAX_AGE_DAYS + 1))
        est = self.pricing.estimate(dict(self.mine), self.market, weapon="x", rtype="rifle")
        self.assertEqual(est["price"], self.base["price"])

    def test_vencen_aunque_el_archivo_no_cambie(self):
        self.write(stamp())
        self.assertNotEqual(self.pricing.estimate(dict(self.mine), self.market, weapon="x", rtype="rifle")["price"],
                            self.base["price"])
        futuro = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=calibration.MAX_AGE_DAYS + 1)
        real = calibration.fresh
        with mock.patch.object(calibration, "fresh", side_effect=lambda u: real(u, futuro)):
            est = self.pricing.estimate(dict(self.mine), self.market, weapon="x", rtype="rifle")
        self.assertEqual(est["price"], self.base["price"])

    def test_el_estimado_flojo_tambien_se_calibra(self):
        self.write(stamp())
        lejos = dict(self.mine, stats=[{"slug": "toxin_damage", "value": 90.0, "positive": True}])
        sin = dict(self.pricing.estimate(dict(lejos), self.market, weapon="otra", rtype="rifle"))
        con = self.pricing.estimate(dict(lejos), self.market, weapon="x", rtype="rifle")
        self.assertEqual(sin["confidence"], "baja")
        self.assertEqual(con["price"], round(sin["price"] * 0.8))
        self.assertEqual(con["reasons"][-1]["key"], "calibrado")

    def test_sin_archivo_queda_igual(self):
        est = self.pricing.estimate(dict(self.mine), self.market, weapon="x", rtype="rifle")
        self.assertEqual(est["price"], self.base["price"])


if __name__ == "__main__":
    unittest.main()
