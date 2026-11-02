"""Tests de weapon_data.json: armas y modelo caro/barato que publica la Lambda cada día
(tools/weapon_data_job.py) y que la app baja, valida y usa, con el bundle de respaldo.
Sin red ni base. Uso: python -m unittest discover -s tests"""
import datetime as dt
import importlib.util
import json
import os
import random
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cloudapi
import pricing
from tools import build_estimator_lambda, release
from tools import weapon_data_job as wdj
from tools.estimator_lambda import handler as lambda_handler

HAY_NUMPY = importlib.util.find_spec("numpy") is not None


def stamp(days_ago=0):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def armas(n=pricing.WEAPON_DATA_MIN_WEAPONS, extra=""):
    return {f"arma_{extra}{i}": {"share": {"slash": 1.0}, "type": "Rifle"} for i in range(n)}


MODELO = {"coef": {"icpt": -1.0, "base": 1.0, "+multishot": 2.0}, "base": {"arma_0": 0.5},
          "hi": 0.6, "lo": 0.3, "n": 100}


def doc(updated=None, **kv):
    d = {"schema": pricing.WEAPON_DATA_SCHEMA, "updated": updated or stamp(),
         "weapon_stats": armas(), "tier_model": json.loads(json.dumps(MODELO))}
    d.update(kv)
    return d


class Validar(unittest.TestCase):
    def test_documento_bueno(self):
        ok = pricing.check_weapon_data(doc())
        self.assertIsNotNone(ok)
        self.assertEqual(len(ok[0]), pricing.WEAPON_DATA_MIN_WEAPONS)
        self.assertEqual(ok[1]["hi"], 0.6)

    def test_documentos_rotos(self):
        malos = [None, [], {}, doc(schema=2), doc(updated="ayer"), doc(weapon_stats=armas(10)),
                 doc(weapon_stats={**armas(), "x": {"share": None}}), doc(tier_model={}),
                 doc(tier_model={**MODELO, "coef": {"icpt": "1", "base": 1.0}}),
                 doc(tier_model={**MODELO, "coef": {"icpt": float("nan"), "base": 1.0}}),
                 doc(tier_model={**MODELO, "hi": True}),
                 doc(tier_model={**MODELO, "base": {"arma_0": None}})]
        for d in malos:
            self.assertIsNone(pricing.check_weapon_data(d), str(d)[:80])

    def test_vencido(self):
        now = dt.datetime(2026, 11, 2)
        self.assertTrue(pricing.weapon_data_fresh(now - dt.timedelta(days=59), now))
        self.assertFalse(pricing.weapon_data_fresh(now - dt.timedelta(days=61), now))


class UsoEnLaApp(unittest.TestCase):
    """pricing usa lo bajado si sirve; si falta, no valida o venció, el bundle."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = Path(self.dir) / "weapon_data.json"
        self.llamadas = []
        pricing.set_weapon_data_path(self.path)
        pricing.set_weapon_data_refresh_hook(lambda: self.llamadas.append(1))
        pricing._wd_cache.update(mtime=None, checked=0.0, data=None)
        self.addCleanup(self.restaurar)

    def restaurar(self):
        pricing._wd_path_override = None
        pricing._wd_refresh_hook = None
        pricing._wd_cache.update(mtime=None, checked=0.0, data=None)

    def usar(self, d, edad_s=0):
        self.path.write_text(json.dumps(d), encoding="utf-8")
        t = time.time() - edad_s
        os.utime(self.path, (t, t))
        pricing._wd_cache["checked"] = 0.0
        return pricing._weapon_data()

    def test_usa_lo_bajado(self):
        ws, tm = self.usar(doc(weapon_stats=armas(extra="nueva")))
        self.assertIn("arma_nueva0", ws)
        self.assertIsNotNone(pricing.weapon_stats("arma_nueva0"))
        self.assertEqual(self.llamadas, [])   # recién bajado: no pide otro

    def test_sin_archivo_usa_el_bundle_y_pide_bajarlo(self):
        ws, tm = pricing._weapon_data()
        self.assertEqual(ws, pricing._bundle("weapon_stats.json"))
        self.assertEqual(tm, pricing._bundle("tier_model.json"))
        self.assertEqual(self.llamadas, [1])

    def test_roto_usa_el_bundle(self):
        ws, _ = self.usar({"schema": 1, "weapon_stats": "x"})
        self.assertEqual(ws, pricing._bundle("weapon_stats.json"))
        self.path.write_text("{no es json", encoding="utf-8")
        pricing._wd_cache["checked"] = 0.0
        self.assertEqual(pricing._weapon_data()[0], pricing._bundle("weapon_stats.json"))

    def test_vencido_usa_el_bundle(self):
        ws, _ = self.usar(doc(updated=stamp(pricing.WEAPON_DATA_MAX_AGE_DAYS + 1), weapon_stats=armas(extra="vieja")))
        self.assertNotIn("arma_vieja0", ws)

    def test_archivo_de_mas_de_un_dia_pide_bajarlo_pero_lo_usa(self):
        ws, _ = self.usar(doc(weapon_stats=armas(extra="ayer")), edad_s=25 * 3600)
        self.assertIn("arma_ayer0", ws)
        self.assertEqual(self.llamadas, [1])

    def test_no_mira_el_disco_en_cada_riven(self):
        self.usar(doc())
        with mock.patch.object(Path, "stat", side_effect=AssertionError("miró el disco")):
            for _ in range(100):
                pricing._weapon_data()

    def test_si_el_hook_falla_igual_estima(self):
        pricing.set_weapon_data_refresh_hook(mock.Mock(side_effect=RuntimeError("x")))
        self.assertIsNotNone(pricing._weapon_data())

    def test_tier_con_modelo_propio(self):
        v = {"stats": [{"slug": "multishot", "positive": True}], "rolls": 0, "rank": 0}
        t = pricing.tier("arma_0", v, model=MODELO)
        self.assertEqual(t["level"], "high")          # -1 + 0.5 + 2 = 1.5 -> p 0.82
        self.assertIsNone(pricing.tier("otra", v, model=MODELO))


class Bajar(unittest.TestCase):
    def test_baja_y_escribe_si_valida(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sub" / "weapon_data.json"
            r = mock.Mock(json=lambda: doc(), raise_for_status=lambda: None)
            with mock.patch.object(cloudapi.requests, "get", return_value=r), \
                 mock.patch.object(pricing, "weapon_data_path", return_value=path):
                cloudapi.CloudMixin()._weapon_data_download()
            self.assertIsNotNone(pricing.check_weapon_data(json.loads(path.read_text(encoding="utf-8"))))

    def test_respuesta_rara_no_pisa_lo_que_hay(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "weapon_data.json"
            path.write_text("previo", encoding="utf-8")
            for cuerpo in ([1], {}, doc(schema=9), doc(weapon_stats={})):
                r = mock.Mock(json=lambda c=cuerpo: c, raise_for_status=lambda: None)
                with mock.patch.object(cloudapi.requests, "get", return_value=r), \
                     mock.patch.object(pricing, "weapon_data_path", return_value=path):
                    cloudapi.CloudMixin()._weapon_data_download()
                self.assertEqual(path.read_text(encoding="utf-8"), "previo")

    def test_un_intento_por_hora(self):
        app = cloudapi.CloudMixin()
        llamadas = []
        app._weapon_data_download = lambda: llamadas.append(1)
        with mock.patch.object(cloudapi.time, "time", return_value=50_000.0):
            app.weapon_data_refresh()
            app.weapon_data_refresh()
        with mock.patch.object(cloudapi.time, "time", return_value=50_000.0 + app.ESTIMATOR_RETRY_S):
            app.weapon_data_refresh()
        for h in threading.enumerate():
            if h is not threading.current_thread() and h.daemon:
                h.join(1)
        self.assertEqual(len(llamadas), 2)


def ventas(n, seed=1):
    """Ventas sintéticas: con multishot positivo se venden caras."""
    rnd = random.Random(seed)
    out = []
    t0 = dt.datetime(2026, 10, 1)
    for i in range(n):
        ms = rnd.random() < 0.5
        attrs = [["multishot" if ms else "zoom", 50.0, True], ["critical_chance", 80.0, True]]
        precio = rnd.uniform(100, 300) if ms else rnd.uniform(10, 60)
        if rnd.random() < 0.1:
            precio = rnd.uniform(10, 300)   # ruido
        out.append({"weapon": f"arma_{i % 20}", "price": precio, "attrs": attrs, "rolls": rnd.randint(0, 20),
                    "rank": rnd.choice([0, 8]), "detected_at": t0 + dt.timedelta(minutes=i)})
    return out


class TrainTierFalso(unittest.TestCase):
    """Sin numpy (el CI de Windows no lo tiene): train_tier se reemplaza por uno de mentira."""

    def setUp(self):
        self.fit = mock.Mock(return_value=dict(MODELO, n=999))
        falso = types.ModuleType("train_tier")
        falso.CUT_PRICE, falso.fit = 80, self.fit
        parche = mock.patch.dict(sys.modules, {"train_tier": falso})
        parche.start()
        self.addCleanup(parche.stop)


class Compuertas(TrainTierFalso):
    def elegir(self, nuevas, auc, n_test=2000, prev=None):
        with mock.patch.object(wdj, "holdout", return_value=(auc, n_test)):
            return wdj.choose(nuevas, [{}] * 5000, prev or armas(400, "prev"), dict(MODELO, n=1),
                              now=dt.datetime(2026, 11, 2, 6, 30))

    def test_todo_pasa(self):
        d, rep = self.elegir(armas(400, "nueva"), 0.9)
        self.assertIn("arma_nueva0", d["weapon_stats"])
        self.assertEqual(d["tier_model"]["n"], 999)
        self.assertEqual(d["updated"], "2026-11-02T06:30:00Z")
        self.assertTrue(rep["armas"]["ok"] and rep["modelo"]["ok"])
        self.fit.assert_called_once()   # lo aprobado se reentrena con todas las ventas

    def test_auc_bajo_conserva_el_modelo_anterior(self):
        d, rep = self.elegir(armas(400, "nueva"), wdj.MIN_AUC - 0.01)
        self.assertFalse(rep["modelo"]["ok"])
        self.assertEqual(d["tier_model"]["n"], 1)
        self.assertIn("arma_nueva0", d["weapon_stats"])
        self.fit.assert_not_called()

    def test_pocas_ventas_de_prueba_no_aprueba(self):
        _, rep = self.elegir(armas(400, "nueva"), 0.99, n_test=wdj.MIN_TEST - 1)
        self.assertFalse(rep["modelo"]["ok"])

    def test_lista_de_armas_achicada_conserva_la_anterior(self):
        d, rep = self.elegir(armas(350, "nueva"), 0.9, prev=armas(500, "prev"))   # 350 < 90 % de 500
        self.assertFalse(rep["armas"]["ok"])
        self.assertIn("arma_prev0", d["weapon_stats"])
        self.assertEqual(d["tier_model"]["n"], 999)

    def test_wfcd_caido_conserva_las_armas(self):
        d, rep = self.elegir(None, 0.9)
        self.assertIn("arma_prev0", d["weapon_stats"])

    def test_nada_pasa_no_publica(self):
        d, rep = self.elegir(None, 0.5)
        self.assertIsNone(d)
        self.assertFalse(rep["armas"]["ok"] or rep["modelo"]["ok"])

    def test_auc_separa_bien_y_empata(self):
        modelo = {"coef": {"icpt": -1.0, "base": 0.0, "+multishot": 3.0}, "hi": 0.6, "lo": 0.3,
                  "base": {f"arma_{i}": 0.0 for i in range(20)}}
        limpio = [v for v in ventas(400) if (v["price"] > 80) == (v["attrs"][0][0] == "multishot")]
        score, n = wdj.auc(modelo, limpio)
        self.assertEqual(n, len(limpio))
        self.assertAlmostEqual(score, 1.0)
        plano = {**modelo, "coef": {"icpt": 0.0, "base": 0.0}}
        self.assertAlmostEqual(wdj.auc(plano, limpio)[0], 0.5)
        self.assertEqual(wdj.auc(modelo, [])[0], None)


@unittest.skipUnless(HAY_NUMPY, "sin numpy (CI de Windows)")
class EntrenarDeVerdad(unittest.TestCase):
    def test_holdout_aprueba_un_patron_real(self):
        score, n = wdj.holdout(ventas(6000))
        self.assertGreaterEqual(n, wdj.MIN_TEST)
        self.assertGreater(score, wdj.MIN_AUC)

    def test_choose_arma_un_documento_valido(self):
        d, rep = wdj.choose(armas(400), ventas(6000), armas(400), pricing._bundle("tier_model.json"))
        self.assertTrue(rep["modelo"]["ok"], rep)
        self.assertIsNotNone(pricing.check_weapon_data(d))


class LambdaArmas(unittest.TestCase):
    def setUp(self):
        parche = mock.patch.dict(sys.modules, {"weapon_data_job": wdj})
        parche.start()
        self.addCleanup(parche.stop)

    def test_publica_en_su_clave_y_cierra(self):
        client = mock.MagicMock()
        with mock.patch("estimator_mongo.db_client", return_value=client), \
             mock.patch.object(wdj, "run", return_value=(doc(), {"armas": {"ok": True}})), \
             mock.patch.object(lambda_handler, "publish") as pub:
            out = lambda_handler.handler_armas({}, None)
        self.assertTrue(out["publicado"])
        self.assertEqual(pub.call_args.args[1], "weapon_data.json")
        client.close.assert_called_once()

    def test_sin_documento_falla_y_no_publica(self):
        client = mock.MagicMock()
        with mock.patch("estimator_mongo.db_client", return_value=client), \
             mock.patch.object(wdj, "run", return_value=(None, {"armas": {"ok": False}})), \
             mock.patch.object(lambda_handler, "publish") as pub:
            with self.assertRaises(RuntimeError):
                lambda_handler.handler_armas({}, None)
        pub.assert_not_called()
        client.close.assert_called_once()

    def test_el_zip_lleva_los_modulos_nuevos(self):
        for f in ("weapon_data_job.py", "train_tier.py", "build_weapon_data.py"):
            self.assertIn(f, build_estimator_lambda.FILES)


class Release(unittest.TestCase):
    def test_copia_lo_publicado_al_bundle(self):
        cuerpo = json.dumps(doc(weapon_stats=armas(extra="pub"))).encode()
        r = mock.MagicMock()
        r.__enter__.return_value.read.return_value = cuerpo
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(release.urllib.request, "urlopen", return_value=r):
            self.assertTrue(release.bundle_weapon_data(dest=Path(d)))
            ws = json.loads((Path(d) / "weapon_stats.json").read_text(encoding="utf-8"))
            self.assertIn("arma_pub0", ws)
            self.assertEqual(json.loads((Path(d) / "tier_model.json").read_text(encoding="utf-8"))["hi"], 0.6)

    def test_si_no_baja_deja_los_que_estan(self):
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(release.urllib.request, "urlopen", side_effect=OSError("sin red")):
            self.assertFalse(release.bundle_weapon_data(dest=Path(d)))
            self.assertEqual(list(Path(d).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
