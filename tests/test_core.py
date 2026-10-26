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

    def test_un_caro_parecido_no_decide_solo(self):
        caro = (("critical_chance", 100.0), ("multishot", 80.0), ("zoom", 30.0))
        flojo = (("critical_chance", 100.0), ("fire_rate", 60.0))
        est = pricing.estimate(MINE, [pub(1, 10000, stats=caro), pub(2, 200, stats=flojo), pub(3, 300, stats=flojo)])
        self.assertLess(est["price"], 10000)

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


class ParseHours(unittest.TestCase):
    def test_horas_y_minutos(self):
        self.assertEqual(store.parse_hours("2"), 2)
        self.assertEqual(store.parse_hours("1,5h"), 1.5)
        self.assertEqual(store.parse_hours(" 30m "), 0.5)
        self.assertEqual(store.parse_hours("1 min"), 1 / 60)
        for malo in ("", None, "0", "abc", "-3", "5x"):
            self.assertIsNone(store.parse_hours(malo))


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


    def test_asignar_origen_a_riven_existente(self):
        with tempfile.TemporaryDirectory() as d, store.connect(Path(d) / "t.db") as conn:
            lote = store.add_lot(conn, "rifle", 2, 100)
            store.set_cost(conn, "x1", 30)                      # suelto: suma 30 aparte
            self.assertEqual(store.invested(conn), 130)
            store.assign_lot(conn, "x1", lote, 50)              # pasa al lote: ya no suma suelto
            self.assertEqual(store.invested(conn), 100)
            self.assertEqual(store.costs(conn)["x1"], {"cost": 50.0, "lot_id": lote})
            self.assertEqual(store.get_lot(conn, lote)["remaining"], 1)
            with self.assertRaises(ValueError):                 # ya tiene origen
                store.assign_lot(conn, "x1", lote)
            store.assign_lot(conn, "x2", lote)                  # sin costo: el unitario del lote
            self.assertEqual(store.costs(conn)["x2"]["cost"], 50.0)
            with self.assertRaises(ValueError):                 # el lote se quedó sin rivens
                store.assign_lot(conn, "x3", lote)


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


class SetStatusTest(unittest.TestCase):
    def test_evento_viejo_no_pisa_la_hora_pedida(self):
        import wfm_client
        from datetime import datetime, timedelta, timezone
        c = wfm_client.WFMClient("eyJ" + "a" * 70 + ".b.c")
        ahora = datetime.now(timezone.utc)
        viejo = {"status": "ingame", "statusUntil": (ahora + timedelta(hours=4)).isoformat()}   # mismo estado, hora vieja
        ok = {"status": "ingame", "statusUntil": (ahora + timedelta(minutes=30)).isoformat()}
        c._ws_session = lambda *a, **k: {"status": viejo, "reply": {"route": "@wfm|cmd/status/set:ok", "payload": ok}}
        st = c.set_status("ingame", 30 * 60)
        falta = (datetime.fromisoformat(st["statusUntil"]) - ahora).total_seconds()
        self.assertTrue(29 * 60 < falta <= 30 * 60 + 5, falta)
        c._ws_session = lambda *a, **k: {"status": viejo, "reply": {"route": "@wfm|cmd/status/set:ok", "payload": {"status": "ingame"}}}
        falta = (datetime.fromisoformat(c.set_status("ingame", 30 * 60)["statusUntil"]) - ahora).total_seconds()   # sin hora en la respuesta: la pedida
        self.assertTrue(29 * 60 < falta <= 30 * 60 + 5, falta)



class FeedbackLog(unittest.TestCase):
    def test_encabezado_mas_log_no_pasa_el_limite_del_servidor(self):
        import feedback
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.log"
            p.write_bytes(("linea ñ larga de log\n" * 40000).encode("utf-8"))
            out = feedback.read_log(str(p), "=== Salud ===\n")
        self.assertTrue(out.startswith("=== Salud ==="))
        self.assertLessEqual(len(out.encode("utf-8")), feedback.MAX_LOG)


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


class OrderCacheSingleFlightTest(unittest.TestCase):
    def test_pedidos_simultaneos_del_arma_comparten_un_solo_pedido(self):
        import threading
        import time
        from orders import OrderCache

        class Client:
            calls = 0

            def search_direct(self, weapon, stats=None):
                Client.calls += 1
                time.sleep(0.2)
                if weapon == "falla":
                    raise RuntimeError("429")
                return []

        c = OrderCache(Client(), lambda: [])
        out, errs = [], []

        def run(fn):
            try:
                out.append(fn())
            except Exception as e:
                errs.append(e)

        ts = [threading.Thread(target=run, args=(lambda: c.load("braton"),)) for _ in range(4)]
        ts += [threading.Thread(target=run, args=(lambda: c.targeted("braton", ["a"]),)) for _ in range(3)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(Client.calls, 2)   # uno por load, uno por targeted
        self.assertEqual(len(out), 7)
        # un error llega a todos los que esperaban y el siguiente intento vuelve a pedir
        Client.calls = 0
        ts = [threading.Thread(target=run, args=(lambda: c.load("falla"),)) for _ in range(3)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual((Client.calls, len(errs)), (1, 3))
        with self.assertRaises(RuntimeError):
            c.load("falla")
        self.assertEqual(Client.calls, 2)


class BookTest(unittest.TestCase):
    """state.Book: un solo lugar donde cambian los contratos; todas las copias quedan iguales."""

    def setUp(self):
        from orders import OrderCache
        from state import Book
        self.cache = OrderCache(None, lambda: [])
        self.book = Book(self.cache)

    def contrato(self, i, price, weapon="detron"):
        return {"id": i, "buyout_price": price, "starting_price": price, "item": {"weapon_url_name": weapon}}

    def cargar_arma(self):
        slim = {"id": "otro", "p": 300, "r": 1, "s": [], "nm": "vendedor"}
        self.cache._data["detron"] = {"at": 100, "orders": [dict(self.contrato("mio", 200))],
                                      "market": [{"id": "mio", "p": 200, "r": 1, "s": []}, slim]}

    def test_cambio_de_precio_llega_a_todas_las_copias(self):
        self.cargar_arma()
        self.book.others["mio"] = self.contrato("mio", 200)
        self.book.own_updated(self.contrato("mio", 150))
        self.assertEqual(self.book.own["mio"]["buyout_price"], 150)
        self.assertEqual(self.book.others["mio"]["buyout_price"], 150)
        e = self.cache._data["detron"]
        self.assertEqual(e["orders"][0]["buyout_price"], 150)
        self.assertEqual(e["market"][0]["p"], 150)

    def test_republicar_cambia_el_id_y_el_viejo_desaparece(self):
        self.cargar_arma()
        self.book.put_own(self.contrato("mio", 200))
        self.book.created(self.contrato("nuevo", 200))
        self.book.closed("mio", "detron")
        self.assertEqual(list(self.book.own), ["nuevo"])
        e = self.cache._data["detron"]
        self.assertEqual(e["orders"], [])
        self.assertEqual([o["id"] for o in e["market"]], ["otro"])
        self.assertEqual(e["at"], 0)   # el arma se vuelve a pedir

    def test_cerrar_saca_de_todos_lados(self):
        self.cargar_arma()
        self.book.put_own(self.contrato("mio", 200))
        self.book.others["mio"] = self.contrato("mio", 200)
        self.book.closed("mio")
        self.assertIsNone(self.book.own.get("mio") or self.book.others.get("mio"))
        self.assertEqual([o["id"] for o in self.cache._data["detron"]["market"]], ["otro"])

    def test_crear_expira_el_arma(self):
        self.cargar_arma()
        self.book.created(self.contrato("nuevo", 90))
        self.assertIn("nuevo", self.book.own)
        self.assertEqual(self.cache._data["detron"]["at"], 0)

    def test_get_reconstruye_un_ajeno_desde_el_cache(self):
        self.cargar_arma()
        a = self.book.get("otro")
        self.assertEqual((a["buyout_price"], a["item"]["weapon_url_name"]), (300, "detron"))
        self.assertIn("otro", self.book.others)
        self.assertIsNone(self.book.get("no-existe"))

    def test_lista_nueva_de_la_api_reemplaza_los_propios(self):
        self.book.put_own(self.contrato("viejo", 10))
        self.book.own_fetched([self.contrato("a", 1), self.contrato("b", 2)])
        self.assertEqual(sorted(self.book.own), ["a", "b"])

    def test_tabla_de_ordenes_incluye_las_propias_y_marca_la_abierta(self):
        from types import SimpleNamespace
        from app import Api
        def ord_(i, price, st):
            return {"id": i, "buyout_price": price, "starting_price": price, "item": {"weapon_url_name": "detron", "attributes": []},
                    "owner": {"ingame_name": "x", "status": st}}
        self.cache._data["detron"] = {"at": 9e12, "orders": [ord_("otro", 300, "ingame")], "market": [{"c": 1}]}
        mia = dict(ord_("mia", 1, "offline"), owner="id-de-usuario")   # invisible: el caché no la trae; owner como id
        self.book.put_own(mia)
        self.book.put_own(dict(ord_("oculta", 5, "offline"), visible=False))
        self.book.put_own(dict(ord_("otra-arma", 5, "offline"), item={"weapon_url_name": "braton", "attributes": []}))
        yo = SimpleNamespace(_cache=self.cache, _book=self.book, VIEW_MAX_AGE_S=10)
        r = Api.weapon_orders(yo, "detron", current_id="otro")["orders"]
        self.assertEqual([(o["id"], o["mine"], o["current"]) for o in r], [("mia", True, False), ("otro", False, True)])

    def test_tabla_de_ordenes_no_corta_la_propia_cara(self):
        from types import SimpleNamespace
        from app import Api
        def ord_(i, price):
            return {"id": i, "buyout_price": price, "starting_price": price, "item": {"weapon_url_name": "detron", "attributes": []},
                    "owner": {"ingame_name": "x", "status": "ingame"}}
        self.cache._data["detron"] = {"at": 9e12, "orders": [ord_(f"o{n}", n) for n in range(1, 10)], "market": [{"c": 1}]}
        self.book.put_own(ord_("mia", 10000))
        yo = SimpleNamespace(_cache=self.cache, _book=self.book, VIEW_MAX_AGE_S=10)
        ids = [o["id"] for o in Api.weapon_orders(yo, "detron")["orders"]]
        self.assertEqual(ids, [f"o{n}" for n in range(1, 8)] + ["mia"])



def riven(i, price=100, weapon="soma"):
    """Contrato propio crudo, como lo devuelve la API."""
    return {"id": i, "buyout_price": price, "starting_price": price, "visible": True,
            "item": {"weapon_url_name": weapon, "name": "Riven", "attributes": []}}


class ClosedStoreTest(unittest.TestCase):
    """Editar, borrar y transmutar contratos cerrados (feedback de testers)."""

    def test_set_sold_price(self):
        with tempfile.TemporaryDirectory() as d, store.connect(Path(d) / "t.db") as conn:
            store.log_event(conn, riven("c1"), "close")
            store.log_sale_hours(conn, "c1", 5)
            self.assertTrue(store.set_sold_price(conn, "c1", 150))
            self.assertEqual(store.closed_auctions(conn)[0]["sold_price"], 150)
            self.assertTrue(store.set_sold_price(conn, "c1", None))
            self.assertIsNone(store.closed_auctions(conn)[0]["sold_price"])
            self.assertNotIn("c1", store.sale_hours(conn))
            self.assertFalse(store.set_sold_price(conn, "nada", 10))

    def test_delete_closed_saca_el_costo_suelto_pero_no_el_lote(self):
        with tempfile.TemporaryDirectory() as d, store.connect(Path(d) / "t.db") as conn:
            store.add_lot(conn, "rifle", 2, 40)
            lot = store.lots(conn)[0]["id"]
            store.log_event(conn, riven("suelto"), "close")
            store.set_cost(conn, "suelto", 30)
            store.log_event(conn, riven("delote"), "close")
            store.assign_lot(conn, "delote", lot, 20)
            self.assertEqual(store.invested(conn), 70)
            self.assertTrue(store.delete_closed(conn, "suelto"))
            self.assertTrue(store.delete_closed(conn, "delote"))
            self.assertEqual(store.closed_auctions(conn), [])
            self.assertEqual(store.invested(conn), 40)
            self.assertFalse(store.delete_closed(conn, "suelto"))

    def test_mark_transmuted(self):
        with tempfile.TemporaryDirectory() as d, store.connect(Path(d) / "t.db") as conn:
            store.log_event(conn, riven("c1"), "close")
            store.log_event(conn, riven("c2"), "close")
            store.mark_transmuted(conn, ["c1"])
            t = {c["auction"]["id"]: bool(c["auction"].get("transmuted")) for c in store.closed_auctions(conn)}
            self.assertEqual(t, {"c1": True, "c2": False})


class ClosedApiTest(unittest.TestCase):
    """Api.set_sold / delete_closed / transmute / close contra una base temporal y un cliente falso."""

    def setUp(self):
        from unittest import mock
        from app import Api
        from orders import OrderCache
        from state import Book
        from wfm_client import WFMError
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        db = Path(self.tmp.name) / "t.db"
        orig = store.connect
        p = mock.patch.object(store, "connect", lambda *a, **k: orig(db))
        p.start()
        self.addCleanup(p.stop)
        self.web = {}          # contratos que "existen" en warframe.market
        self.closed_web = []
        test = self

        class Client:
            def my_auctions(self):
                return list(test.web.values())

            def close_auction(self, auction_id):
                if auction_id not in test.web:
                    raise WFMError("Not found")
                test.web.pop(auction_id)
                test.closed_web.append(auction_id)

        self.api = Api.__new__(Api)
        self.api._book = Book(OrderCache(None, lambda: []))
        self.api.client = Client()

    def publish(self, i):
        self.web[i] = riven(i)
        self.api._book.put_own(self.web[i])

    def closed_row(self, i):
        return next(c for c in self.api.local()["closed"] if c["id"] == i)

    def test_set_sold(self):
        with store.connect() as conn:
            store.log_event(conn, riven("c1"), "close")
        self.assertIsNone(self.closed_row("c1")["sold_price"])
        self.assertEqual(self.api.set_sold("c1", "120")["closed"][0]["sold_price"], 120)
        self.assertIsNone(self.api.set_sold("c1", "")["closed"][0]["sold_price"])
        self.assertIn("negativo", self.api.set_sold("c1", -5)["error"])
        self.assertIn("cerrados", self.api.set_sold("nada", 10)["error"])
        self.assertIn("error", self.api.set_sold("c1", "abc"))

    def test_set_sold_rechaza_publicados_y_transmutados(self):
        self.publish("p1")
        with store.connect() as conn:
            store.log_event(conn, riven("p1"), "close")   # cerrado viejo con el mismo id, pero sigue publicado
            store.log_event(conn, riven("t1"), "close")
            store.mark_transmuted(conn, ["t1"])
        self.assertIn("cerrados", self.api.set_sold("p1", 10)["error"])
        self.assertIn("transmutación", self.api.set_sold("t1", 10)["error"])

    def test_delete_closed(self):
        with store.connect() as conn:
            store.log_event(conn, riven("c1"), "close")
            store.set_cost(conn, "c1", 25)
        res = self.api.delete_closed("c1")
        self.assertEqual(res["closed"], [])
        self.assertEqual(res["invested"], 0)
        self.assertIn("error", self.api.delete_closed("c1"))
        self.publish("p1")
        self.assertIn("error", self.api.delete_closed("p1"))

    def test_close_contrato_borrado_desde_la_web(self):
        """Si el riven se borra desde warframe.market, la publicación no tiene que quedar colgada."""
        self.publish("x")
        self.web.pop("x")                      # lo borró desde la web
        res = self.api.close("x")
        self.assertTrue(res.get("gone"))
        self.assertNotIn("error", res)
        self.assertNotIn("x", self.api._book.own)
        self.assertEqual(self.closed_row("x")["id"], "x")

    def test_current_contrato_borrado_lo_saca_del_book(self):
        from app import GoneError
        self.publish("x")
        self.web.pop("x")
        with self.assertRaises(GoneError):
            self.api._current("x")
        self.assertNotIn("x", self.api._book.own)
        self.assertTrue(self.api.close("x").get("gone"))

    def test_close_normal_no_marca_gone(self):
        self.publish("ok")
        res = self.api.close("ok", sold_price=90)
        self.assertNotIn("gone", res)
        self.assertEqual(self.closed_web, ["ok"])
        self.assertEqual(self.closed_row("ok")["sold_price"], 90)

    def test_transmute_con_publicados_y_cerrados_sin_vender(self):
        for i in ("p1", "p2"):
            self.publish(i)
        with store.connect() as conn:
            store.log_event(conn, riven("c1"), "close")
            store.log_event(conn, riven("c2"), "close")
            store.log_event(conn, riven("v1"), "close", sold_price=50)
            for i, cost in (("p1", 10), ("p2", 10), ("c1", 5), ("c2", 5)):
                store.set_cost(conn, i, cost)
        self.assertIn("error", self.api.transmute(["p1", "p2", "c1", "v1"], "rifle"))   # el vendido no vale
        res = self.api.transmute(["p1", "p2", "c1", "c2"], "rifle")
        self.assertNotIn("error", res)
        self.assertEqual(sorted(res["transmuted"]), ["p1", "p2"])
        self.assertEqual(sorted(self.closed_web), ["p1", "p2"])
        rows = {c["id"]: c["transmuted"] for c in res["closed"]}
        self.assertEqual(rows, {"p1": True, "p2": True, "c1": True, "c2": True, "v1": False})
        lot = res["lots"][0]
        self.assertEqual((lot["riven_type"], lot["total_cost"]), ("rifle", 30))
        self.assertEqual(res["invested"], 30)
        # ya usados: no se pueden transmutar de nuevo
        self.assertIn("error", self.api.transmute(["c1", "c2", "p1", "p2"], "rifle"))

class SearchPaceTest(unittest.TestCase):
    """Tope por minuto de la búsqueda de contratos: Cloudflare frena con 11-14 en un minuto."""
    def test_la_decima_busqueda_espera_y_lo_demas_no(self):
        import ratelimit
        now = [1000.0]
        slept = []
        def sleep(s):
            slept.append(s); now[0] += s
        q = ratelimit.RequestQueue(clock=lambda: now[0], sleep=sleep)
        job = lambda label: ratelimit._Job(lambda: None, label)
        for i in range(ratelimit.SEARCH_PER_MIN):
            q._wait_slot(job("get_rivens_by_weapon: syam")); now[0] += 2
        self.assertEqual(q.search_room(), 0)
        before = sum(slept)
        q._wait_slot(job("get_my_profile"))   # otros pedidos no cuentan para este tope
        self.assertLess(sum(slept) - before, 2)
        q._wait_slot(job("get_rivens_by_weapon: onos"))
        self.assertGreater(sum(slept) - before, 30)   # esperó a que saliera la primera del minuto
        self.assertGreaterEqual(now[0] - 1000.0, ratelimit.SEARCH_WINDOW_S)


class TierTest(unittest.TestCase):
    def view(self, *stats):
        return {"stats": [{"slug": a, "value": 1, "positive": b} for a, b in stats], "rolls": 0, "rank": 8}

    def test_etiqueta_por_arma_y_stats(self):
        arma = next(iter(pricing._json.loads((Path(pricing.__file__).parent / "data" / "tier_model.json").read_text("utf-8"))["base"]))
        r = pricing.tier(arma, self.view(("critical_damage", True), ("multishot", True)))
        self.assertIn(r["level"], ("high", "mid", "low"))
        self.assertTrue(0 <= r["p"] <= 1)

    def test_arma_sin_ventas_no_se_etiqueta(self):
        self.assertIsNone(pricing.tier("arma_que_no_existe", self.view(("zoom", True))))


if __name__ == "__main__":
    unittest.main()
