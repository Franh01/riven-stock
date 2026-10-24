"""Tests de la lógica pura (precio, stock, oportunidades, reroll, invertido). Sin red ni la base real.
Uso: python -m unittest discover -s tests   (desde la raíz del repo)"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import opportunities
import pricing
import reroll
import stockcheck
import store


def pub(i, price, stats=(("critical_chance", 100.0), ("multishot", 80.0)), neg=None, status="ingame", rolls=5):
    s = [[slug, v, True] for slug, v in stats] + ([[neg, -50.0, False]] if neg else [])
    return {"id": f"a{i}", "p": price, "st": status, "s": s, "r": rolls, "n": "Riven", "k": 8, "nm": f"v{i}"}


MINE = {"id": "mine", "price": 100, "rolls": 5, "rank": 8,
        "stats": [{"slug": "critical_chance", "value": 100.0, "positive": True},
                  {"slug": "multishot", "value": 80.0, "positive": True}]}


class Pricing(unittest.TestCase):
    def test_sin_mercado_o_sin_positivos(self):
        self.assertIsNone(pricing.estimate(MINE, []))
        self.assertIsNone(pricing.estimate({"stats": [], "rolls": 0}, [pub(1, 50)]))

    def test_mediana_de_comparables_iguales(self):
        est = pricing.estimate(MINE, [pub(i, 200) for i in range(8)], exclude_id="mine")
        self.assertEqual(est["price"], 200)
        self.assertEqual(est["confidence"], "alta")

    def test_ignora_el_propio_y_precios_vacios(self):
        market = [pub(i, 200) for i in range(4)] + [{**pub(9, 1), "id": "mine"}, pub(10, 0)]
        est = pricing.estimate(MINE, market, exclude_id="mine")
        self.assertEqual(est["n"], 4)

    def test_stats_distintos_no_son_comparables(self):
        otros = [pub(i, 500, stats=(("zoom", 10.0), ("recoil", -5.0))) for i in range(5)]
        self.assertIsNone(pricing.estimate(MINE, otros))

    def test_techo_por_comparables_baratos(self):
        # 3+ muy parecidos a 40 y uno carísimo: el techo 2.5x de la mediana cercana lo recorta
        market = [pub(i, 40) for i in range(4)] + [pub(9, 4000)]
        est = pricing.estimate(MINE, market, exclude_id="mine")
        self.assertLessEqual(est["price"], 100)

    def test_wquantile(self):
        self.assertEqual(pricing._wquantile([(10, 1), (20, 1), (30, 1)], 0.5), 20)


class Stock(unittest.TestCase):
    MARKET = [pub(i, 200) for i in range(8)]

    def test_caro(self):
        self.assertIn("caro", stockcheck.position({**MINE, "price": 400}, self.MARKET, None, 0, 0)["tags"])

    def test_barato(self):
        self.assertIn("barato", stockcheck.position({**MINE, "price": 100}, self.MARKET, None, 0, 0)["tags"])

    def test_en_rango_y_estancado(self):
        pos = stockcheck.position({**MINE, "price": 200}, self.MARKET, None, 50, 48)
        self.assertEqual(pos["tags"], ["estancado"])

    def test_sin_datos_confiables(self):
        self.assertIsNone(stockcheck.position(MINE, self.MARKET[:2], None, 0, 0))


class Opportunities(unittest.TestCase):
    def test_detecta_el_barato(self):
        market = [pub(i, 200) for i in range(10)] + [pub(99, 50)]
        res = opportunities.find(market, None, 30, 15)
        self.assertEqual([r["id"] for r in res], ["a99"])
        self.assertEqual(res[0]["gain"], res[0]["estimate"] - 50)

    def test_umbral_y_skip(self):
        market = [pub(i, 200) for i in range(10)] + [pub(99, 50)]
        self.assertEqual(opportunities.find(market, None, 30, 15, skip_ids={"a99"}), [])
        self.assertEqual(opportunities.find(market, None, 90, 15), [])

    def test_sin_oportunidad_si_todo_cuesta_igual(self):
        self.assertEqual(opportunities.find([pub(i, 200) for i in range(10)], None, 30, 15), [])


class Reroll(unittest.TestCase):
    def test_kuva_cost(self):
        self.assertEqual(reroll.kuva_cost(0, 3), 900 + 1000 + 1200)
        self.assertEqual(reroll.kuva_cost(9, 2), 3500 * 2)   # tope en la última tirada


class Invertido(unittest.TestCase):
    def test_lotes_y_sueltos(self):
        with tempfile.TemporaryDirectory() as d, store.connect(Path(d) / "t.db") as conn:
            store.add_lot(conn, "rifle", 5, 100)
            store.add_lot(conn, "rifle", 2, 999, from_transmute=True)   # no suma: ya está en los sacrificados
            store.set_cost(conn, "x1", 30)
            lote = store.add_lot(conn, "pistol", 1, 20)
            store.set_cost(conn, "x2", 20, lot_id=lote)                  # ya cuenta en el lote
            self.assertEqual(store.invested(conn), 100 + 20 + 30)


class LoopHealth(unittest.TestCase):
    def test_report(self):
        import loophealth
        loophealth.beat("t_ok", 10)
        loophealth.beat("t_mal", 10, ValueError("boom"))
        r = loophealth.report()
        self.assertIn("t_ok: último ciclo OK hace", r)
        self.assertIn("t_mal: último ciclo OK nunca | último error hace", r)
        self.assertIn("boom", r)
        self.assertNotIn("t_ok: último ciclo OK hace 0s ATRASADO", r)


class Crashes(unittest.TestCase):
    def test_lock_y_crash(self):
        import os
        import crashes
        d = Path(tempfile.mkdtemp())
        crashes.begin(d, d / "x.log", "1.0")
        lock = d / "crashes" / "running.lock"
        self.assertTrue(lock.exists())
        crashes.end()
        self.assertFalse(lock.exists())
        # lock de un proceso muerto = crash; de un proceso vivo (otra instancia) = no
        lock.write_text('{"v": "0.9", "pid": 4000000}')
        crashes.begin(d, d / "x.log", "1.0")
        self.assertEqual(len(crashes.pending()), 1)
        lock.write_text('{"v": "0.9", "pid": %d}' % os.getppid())
        crashes.begin(d, d / "x.log", "1.0")
        self.assertEqual(len(list((d / "crashes").glob("crash-*.txt"))), 1)   # sin cambios; esta instancia queda sin _dir
        self.assertEqual(crashes.pending(), [])


class CloudflareTest(unittest.TestCase):
    def test_detecta_challenge_y_no_confunde_un_403_normal(self):
        from types import SimpleNamespace as R
        import wfm_client
        self.assertTrue(wfm_client.is_cloudflare_challenge(R(status_code=403, headers={"cf-mitigated": "challenge"})))
        self.assertFalse(wfm_client.is_cloudflare_challenge(R(status_code=403, headers={})))
        self.assertFalse(wfm_client.is_cloudflare_challenge(R(status_code=200, headers={"cf-mitigated": "challenge"})))

    def test_request_levanta_cloudflare_error_sin_pedir_renovar_el_token(self):
        from types import SimpleNamespace as R
        import wfm_client
        c = wfm_client.WFMClient("eyJ" + "a" * 70 + ".b.c")
        res = R(status_code=403, headers={"cf-mitigated": "challenge"}, text="Just a moment...", ok=False)
        orig = wfm_client.QUEUE.submit
        wfm_client.QUEUE.submit = lambda fn, label=None: res
        try:
            with self.assertRaises(wfm_client.CloudflareError) as cm:
                c.get("/v1/profile/auctions", auth=True)
        finally:
            wfm_client.QUEUE.submit = orig
        self.assertIn("Cloudflare es el servicio", str(cm.exception))


if __name__ == "__main__":
    unittest.main()


class OrderCacheForgetTest(unittest.TestCase):
    def test_forget_saca_el_contrato_y_expira_el_arma(self):
        from orders import OrderCache
        c = OrderCache(None, lambda: [])
        c._data["detron"] = {"at": 100, "orders": [{"id": "viejo"}, {"id": "otro"}], "market": [{"id": "viejo"}, {"id": "otro"}]}
        c._targeted[("detron", ("x",))] = (5, [{"id": "viejo"}])
        c.forget("viejo", "detron")
        e = c._data["detron"]
        self.assertEqual([o["id"] for o in e["orders"]], ["otro"])
        self.assertEqual([o["id"] for o in e["market"]], ["otro"])
        self.assertEqual(c._targeted[("detron", ("x",))][1], [])
        self.assertEqual(e["at"], 0)
