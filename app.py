"""Riven Stock: app desktop (ventana pywebview + interfaz HTML en ui/)."""

import ctypes
import json
import sys
import threading
import traceback
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import websocket
import webview

import store
import updater
from orders import OrderCache
from pricing import estimate
from wfm_client import SEARCH_CAP, WFMClient, WFMError, cheapest_ingame

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
ICON = ROOT / "assets" / "icon.ico"
BASES = ROOT / "data" / "riven_bases.json"  # lo genera tools/derive_riven_bases.py
TITLE = "Riven Stock"


class Api:
    """Métodos que la interfaz llama con window.pywebview.api.<método>()."""

    def __init__(self):
        self.client = WFMClient()
        self._seen = {}  # id -> último contrato propio leído de la API (crudo)
        self._market = {}  # id -> contrato ajeno visto en la pestaña Mercado (crudo)
        self._online = False   # lo mantiene el hilo contador
        self._cache = OrderCache(self.client, self._wanted_weapons, str(store.DB_PATH.parent / "cache" / "order_cache.json"))

    def _rtype(self, weapon):
        return next((w.get("rivenType") for w in self.client.riven_weapons() if w["slug"] == weapon), None)

    def catalog(self):
        weapons = [
            {"slug": w["slug"], "name": w["i18n"]["en"]["name"], "type": w["rivenType"],
             "group": w.get("group"), "disposition": w.get("disposition")}
            for w in self.client.riven_weapons()
        ]
        stats = [
            {"slug": a["slug"], "name": a["i18n"]["en"]["name"], "unit": a.get("unit"),
             "positiveOnly": bool(a.get("positiveOnly")), "exclusiveTo": a.get("exclusiveTo") or [],
             "prefix": a.get("prefix"), "suffix": a.get("suffix")}
            for a in self.client.riven_attributes()
        ]
        return {
            "weapons": sorted(weapons, key=lambda w: w["name"]),
            "stats": sorted(stats, key=lambda s: s["name"]),
            # Valor base de cada stat por tipo de riven, para sugerir el orden del nombre.
            "bases": json.loads(BASES.read_text(encoding="utf-8")) if BASES.exists() else {},
        }

    # ---- Preferencias (locales) -------------------------------------------

    SETTING_KEYS = {"auto_ingame", "mine_sort", "invisible_on_close",
                    "autodrop_enabled", "autodrop_hours", "autodrop_amount", "autodrop_floor"}

    # ---- Actualizaciones ----
    def get_version(self):
        return updater.version_actual()

    def get_changelog(self):
        try:
            return (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        except OSError:
            return ""

    def check_update(self):
        """{version, notas} si hay una versión nueva; {} si no; {error} si no se pudo consultar."""
        try:
            info = updater.buscar_actualizacion()
        except Exception as e:
            return {"error": f"No se pudo buscar actualizaciones: {e}"}
        self._update_info = info
        return {"version": info["version"], "notas": info["notas"]} if info else {}

    def install_update(self):
        info = getattr(self, "_update_info", None)
        if not info:
            return {"error": "No hay una actualización pendiente."}
        try:
            staging, nuevo = updater.preparar(info)
            updater.lanzar_aplicador(staging, nuevo)
        except Exception as e:
            return {"error": str(e)}
        # Cierra por el camino normal (queda Invisible); el aplicador espera y reemplaza.
        threading.Timer(1.0, lambda: self._window.destroy()).start()
        return {"ok": True}

    def get_settings(self):
        with store.connect() as conn:
            return store.settings(conn)

    def set_setting(self, key, value):
        if key not in self.SETTING_KEYS:
            return {"error": f"Preferencia desconocida: {key}"}
        with store.connect() as conn:
            store.set_setting(conn, key, value)
        return {"ok": True}

    # ---- Estado del usuario (Invisible / Online / En juego) ----------------

    def status(self):
        try:
            return {"status": self.client.get_status()}
        except (WFMError, OSError, websocket.WebSocketException) as e:
            return {"error": str(e)}

    def set_status(self, status, minutes):
        try:
            return {"status": self.client.set_status(status, int(minutes) * 60)}
        except (WFMError, ValueError, OSError, websocket.WebSocketException) as e:
            return {"error": str(e)}

    # ---- Horas online efectivas ---------------------------------------------

    TICK_S = 60          # una muestra por minuto
    TICK_CAP_S = 120     # tope por muestra: una suspensión de la PC no suma horas
    STATUS_REFRESH_S = 300
    RENEW_BEFORE_S = 600

    def start_counter(self):
        try:
            with store.connect() as conn:
                store.purge_old(conn)
        except Exception:
            pass
        self._stop = threading.Event()
        threading.Thread(target=self._counter_loop, daemon=True).start()
        threading.Thread(target=self._drop_loop, daemon=True).start()
        self._cache.start()

    def stop_counter(self):
        if getattr(self, "_stop", None):
            self._stop.set()
        self._cache.stop()

    def _counter_loop(self):
        last = time.monotonic()
        st, st_at = None, 0.0
        while not self._stop.wait(self.TICK_S):
            now = time.monotonic()
            elapsed = min(now - last, self.TICK_CAP_S)
            last = now
            try:
                if st is None or now - st_at > self.STATUS_REFRESH_S:
                    st, st_at = self.client.get_status(), now
                until = st.get("statusUntil") if st else None
                left = (datetime.fromisoformat(until.replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds() if until else 0
                self._online = bool(st and st.get("status") in ("online", "ingame") and left > 0)
                if self._online:
                    with store.connect() as conn:
                        store.add_online_seconds(conn, elapsed)
                        # solo cuentan los rivens visibles: uno oculto no está a la venta
                        store.add_riven_seconds(conn, [i for i, a in list(self._seen.items()) if a.get("visible", True)], elapsed)
                    if left < self.RENEW_BEFORE_S:   # el servidor corta a las 4 h: renovar mientras la app esté abierta
                        st, st_at = self.client.set_status(st["status"], 240 * 60), now
            except Exception:
                st = None   # sin red o error de la API: no suma ese minuto y reintenta

    # ---- Caché de órdenes y baja automática ---------------------------------

    DROP_PASS_S = 300      # cada cuánto corre el motor de baja
    VIEW_MAX_AGE_S = 600   # al abrir un riven, si los datos son más viejos se vuelven a pedir
    CACHE_MAX_AGE_S = 900  # el motor no decide con órdenes más viejas que esto

    def activity(self):
        """La interfaz avisa que se está usando; el caché solo carga en idle."""
        self._cache.touch()
        return {"ok": True}

    def _wanted_weapons(self):
        """Armas de mis rivens visibles, primero las de los rivens más cerca de su umbral de horas."""
        with store.connect() as conn:
            cfg, hours = store.settings(conn), store.riven_hours(conn)
        base = cfg.get("autodrop_hours", 10)
        score = {}
        for i, a in list(self._seen.items()):
            if not a.get("visible", True):
                continue
            h = hours.get(i, {})
            ratio = h.get("hours", 0) / (h.get("hours_override") or base or 1)
            w = a["item"]["weapon_url_name"]
            score[w] = max(score.get(w, 0), ratio)
        return sorted(score, key=score.get, reverse=True)

    def weapon_orders(self, weapon):
        """Las 7 órdenes online más baratas del arma, desde el caché (la pide solo si falta)."""
        try:
            e = self._cache.get(weapon, self.VIEW_MAX_AGE_S)
            if not e or "market" not in e:
                e = self._cache.load(weapon)
        except (WFMError, requests.RequestException) as ex:
            return {"error": str(ex)}
        return {"orders": [{**auction_view(a), "seller": a["owner"]["ingame_name"], "status": a["owner"]["status"],
                            "reputation": a["owner"].get("reputation")} for a in e["orders"][:7]],
                "age_s": int(time.time() - e["at"]), "market": e.get("market", [])}

    def notifications(self):
        with store.connect() as conn:
            items = store.notifications(conn)
        return {"items": items, "unread": sum(1 for n in items if not n["read_at"])}

    def mark_read(self, notification_id=None):
        with store.connect() as conn:
            store.mark_read(conn, notification_id)
        return self.notifications()

    def revert_drop(self, drop_id):
        """Vuelve al precio anterior a la baja y apaga la baja automática de ese riven."""
        with store.connect() as conn:
            d = store.get_drop(conn, drop_id)
        if not d or d["reverted_at"]:
            return {"error": "Esa baja ya no se puede revertir."}
        aid = d["auction_id"]
        try:
            cur = self._current(aid)
            new = self.client.update_auction(
                aid, price=d["old_price"], visible=cur["visible"], note=cur.get("note_raw", ""),
                minimal_reputation=cur.get("minimal_reputation", 0))
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        self._seen[aid] = new
        with store.connect() as conn:
            store.log_event(conn, new, "update")
            store.add_price(conn, aid, new["buyout_price"], "revert")
            store.mark_reverted(conn, drop_id, aid)
        return {"auction": auction_view(new), **self.notifications()}

    def set_autodrop(self, auction_id, on):
        with store.connect() as conn:
            store.set_autodrop(conn, auction_id, on)
        return {"ok": True}

    def set_overrides(self, auction_id, hours=None, amount=None, floor=None):
        def num(v, cast):
            try:
                v = cast(v)
                return v if v > 0 else None
            except (TypeError, ValueError):
                return None
        with store.connect() as conn:
            store.set_overrides(conn, auction_id, num(hours, float), num(amount, int), num(floor, int))
        return {"ok": True}

    def riven_summary(self, auction_id):
        """Resumen de un riven: historial de precios, horas y órdenes online más baratas del caché."""
        a = self._seen.get(auction_id)
        foreign = a is None
        if foreign:
            a = self._market.get(auction_id)
        if not a:
            return {"error": "Riven no encontrado."}
        if foreign:
            hist, h = [], None
        else:
            with store.connect() as conn:
                hist = store.price_history(conn, auction_id)
                h = store.riven_hours(conn).get(auction_id)
        weapon = a["item"]["weapon_url_name"]
        orders = self.weapon_orders(weapon)
        view = auction_view(a)
        pool = {o["id"]: o for o in orders.pop("market", [])}
        positives = [s["slug"] for s in view["stats"] if s["positive"]]
        # Consultas por stats: todos juntos y cada par; así entran las publicaciones que de verdad se parecen.
        combos = [positives] if len(positives) >= 2 else []
        if len(positives) == 3:
            combos += [[x, y] for i, x in enumerate(positives) for y in positives[i + 1:]]
        for c in combos:
            try:
                for o in self._cache.targeted(weapon, c):
                    pool[o["id"]] = o
            except (WFMError, requests.RequestException):
                pass
        try:
            rtype = self._rtype(weapon)
        except (WFMError, requests.RequestException):
            rtype = None
        est = estimate(view, list(pool.values()), exclude_id=auction_id, rtype=rtype)
        out = {"auction": view, "history": hist, "hours": h, "orders": orders, "estimate": est}
        if foreign:
            out["market"] = {"seller": a["owner"]["ingame_name"], "status": a["owner"].get("status"),
                             "reputation": a["owner"].get("reputation")}
        return out

    def _drop_loop(self):
        while not self._stop.wait(self.DROP_PASS_S):
            try:
                r = self.autodrop_pass() if self._online else "offline"
                self._log_pass(r)
            except Exception:
                self._log_pass(traceback.format_exc())

    def _log_pass(self, result):
        try:
            p = store.DB_PATH.parent / "cache" / "autodrop.log"
            with open(p, "a", encoding="utf-8") as f:
                f.write(f"{store.now_iso()} {result}" + chr(10))
        except Exception:
            pass

    def autodrop_pass(self):
        """Una pasada: baja como mucho UN riven. Decide solo con órdenes del caché."""
        with store.connect() as conn:
            cfg, hours = store.settings(conn), store.riven_hours(conn)
        if not cfg.get("autodrop_enabled", False):
            return None
        for aid, a in sorted(self._seen.items(), key=lambda kv: kv[1]["item"]["weapon_url_name"]):
            h = hours.get(aid)
            if not a.get("visible", True) or not h or not h["autodrop_on"]:
                continue
            need = h["hours_override"] or cfg.get("autodrop_hours", 10)
            if h["hours"] < need:
                continue
            e = self._cache.get(a["item"]["weapon_url_name"], self.CACHE_MAX_AGE_S)
            if not e:
                continue   # el caché lo carga en idle; sin datos frescos no se decide
            price = a["buyout_price"]
            others = [o["buyout_price"] for o in e["orders"] if o["id"] != aid]
            amount = h["amount_override"] or cfg.get("autodrop_amount", 5)
            floor = h["floor_override"] or cfg.get("autodrop_floor", 10)
            new = max(price - amount, floor)
            if not others or price <= min(others) or new >= price:
                with store.connect() as conn:   # ya es el más barato (o está en el piso): otras N horas
                    store.reset_riven_hours(conn, aid)
                continue
            return self._apply_drop(aid, new)
        return None

    def _apply_drop(self, aid, new):
        try:
            cur = self._current(aid)
            old = cur["buyout_price"]
            if new >= old:
                return None
            upd = self.client.update_auction(
                aid, price=new, visible=cur["visible"], note=cur.get("note_raw", ""),
                minimal_reputation=cur.get("minimal_reputation", 0))
        except (WFMError, requests.RequestException):
            return None
        self._seen[aid] = upd
        item = upd["item"]
        text = f"Bajé {item['weapon_url_name']} {item.get('name', '')} de {old} a {new} pt".replace("  ", " ")
        with store.connect() as conn:
            store.log_event(conn, upd, "update")
            store.add_price(conn, aid, new, "auto")
            store.add_drop(conn, aid, old, new, text)
            store.reset_riven_hours(conn, aid)
        return {"id": aid, "old": old, "new": new}

    def online_hours(self):
        with store.connect() as conn:
            return {"hours": store.online_seconds(conn) / 3600}

    def on_closing(self):
        """Al cerrar la app: Invisible, salvo que el usuario lo haya desactivado.
        Cancela el cierre, muestra "Cerrando…" y cierra de verdad cuando termina."""
        if getattr(self, "_closing", False):
            return getattr(self, "_close_ok", False)
        self._closing = True
        self.stop_counter()
        # El evento corre en el hilo de la interfaz: evaluar JS acá se bloquea a sí mismo.
        threading.Thread(target=self._finish_close, daemon=True).start()
        return False

    def _finish_close(self):
        try:
            self._window.evaluate_js("showClosing()")
        except Exception:
            pass
        try:
            with store.connect() as conn:
                if store.settings(conn).get("invisible_on_close", True):
                    self.client.set_status("invisible", 60)
        except Exception:
            pass   # si falla, el estado vence solo
        self._close_ok = True
        self._window.destroy()

    def search(self, weapon, n=7):
        """Precio de referencia: las `n` ventas directas más baratas del arma (cualquier stat)
        de vendedores en juego."""
        try:
            found = self.client.search_direct(weapon)
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        top = cheapest_ingame(found, n)
        return {
            "results": [
                {**auction_view(a), "seller": a["owner"]["ingame_name"],
                 "reputation": a["owner"].get("reputation")}
                for a in top
            ],
            # Si la búsqueda llegó al corte y no hubo `n` in game, puede haber más fuera del corte.
            "maybe_incomplete": len(found) >= SEARCH_CAP - 10 and len(top) < n,
        }

    def market_search(self, weapon, stats=(), n=150):
        """Pestaña Mercado: ventas directas de un arma (con esos stats positivos, si hay), de las
        más baratas a las más caras; vendedores en juego/online primero en el desempate."""
        stats = [s for s in stats if s]
        try:
            found = self.client.search_direct(weapon, stats)
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        rows = [a for a in found if a.get("visible", True) and not a.get("closed") and not a.get("private")]
        rows = [a for a in rows if a["owner"].get("status") in ("ingame", "online")] or rows
        rows.sort(key=lambda a: a["buyout_price"])
        rows = rows[:n]
        for a in rows:
            self._market[a["id"]] = a
        return {"results": [{**auction_view(a), "seller": a["owner"]["ingame_name"],
                             "status": a["owner"].get("status"), "reputation": a["owner"].get("reputation")}
                            for a in rows],
                "total": len(found)}

    # ---- Mis contratos ----------------------------------------------

    def my_auctions(self):
        """Todo lo que muestra la pantalla principal: contratos abiertos (API), y del registro
        local los cerrados, los costos, el stock unveiled y lo invertido."""
        try:
            auctions = [a for a in self.client.my_auctions() if a["is_direct_sell"]]
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        auctions.sort(key=lambda a: (not a["visible"], a["item"]["weapon_url_name"]))
        self._seen = {a["id"]: a for a in auctions}
        with store.connect() as conn:
            store.sync_rivens(conn, auctions)
        return {"auctions": [auction_view(a) for a in auctions], **self.local()}

    def local(self):
        """Solo los datos locales (no llama a la API)."""
        with store.connect() as conn:
            return {
                "closed": [{**auction_view(c["auction"]), "sold_price": c["sold_price"],
                            "closed_at": c["closed_at"]} for c in store.closed_auctions(conn)],
                "costs": store.costs(conn),
                "lots": store.lots(conn),
                "invested": store.invested(conn),
                "hours": store.riven_hours(conn),
            }

    # ---- Costos y stock unveiled (solo local) ----------------------------

    def set_cost(self, auction_id, cost):
        try:
            with store.connect() as conn:
                store.set_cost(conn, auction_id, None if cost in (None, "") else float(cost))
        except (ValueError, store.sqlite3.Error) as e:
            return {"error": str(e)}
        return self.local()

    def add_lot(self, riven_type, quantity, cost, cost_is_total=True, note=""):
        try:
            quantity = int(quantity)
            if quantity < 1:
                raise ValueError("La cantidad tiene que ser al menos 1")
            total = float(cost) if cost_is_total else float(cost) * quantity
            with store.connect() as conn:
                store.add_lot(conn, riven_type, quantity, total, note)
        except (ValueError, TypeError, store.sqlite3.Error) as e:
            return {"error": str(e)}
        return self.local()

    def discard_from_lot(self, lot_id):
        """Un riven del lote se abrió y no se va a publicar."""
        try:
            with store.connect() as conn:
                store.open_from_lot(conn, int(lot_id), None)
        except (ValueError, store.sqlite3.Error) as e:
            return {"error": str(e)}
        return self.local()

    def transmute(self, auction_ids, riven_type):
        """Transmutación del juego: 4 rivens publicados se cierran (sin venta) y entra al stock
        unveiled 1 riven sin abrir del tipo que salió, con el costo de los 4 sumado. Ese costo ya
        está en "invertido" por los rivens sacrificados, así que el lote no lo suma otra vez."""
        ids = list(dict.fromkeys(auction_ids or []))
        if len(ids) != 4:
            return {"error": "Hay que elegir exactamente 4 rivens"}
        if riven_type not in store.RIVEN_TYPES:
            return {"error": "Tipo de riven inválido"}
        missing = [i for i in ids if i not in self._seen]
        if missing:
            return {"error": "Algún riven ya no está en la lista: actualizá y probá de nuevo"}
        with store.connect() as conn:
            known = store.costs(conn)
        total_cost = sum(known.get(i, {}).get("cost", 0) for i in ids)
        closed = []
        for auction_id in ids:
            res = self.close(auction_id)
            if "error" in res:
                note = f" Ya se cerraron {len(closed)} antes del error." if closed else ""
                return {"error": res["error"] + note, "transmuted": closed}
            closed.append(auction_id)
        try:
            with store.connect() as conn:
                store.add_lot(conn, riven_type, 1, total_cost, "Transmutación de 4 rivens", from_transmute=True)
        except store.sqlite3.Error as e:
            return {"error": f"Se cerraron los 4 pero no se pudo cargar el stock: {e}", "transmuted": closed}
        return {**self.local(), "transmuted": closed}

    def delete_lot(self, lot_id):
        try:
            with store.connect() as conn:
                store.delete_lot(conn, int(lot_id))
        except (ValueError, store.sqlite3.Error) as e:
            return {"error": str(e)}
        return self.local()

    def _current(self, auction_id, fresh=True):
        """El contrato tal como está en la API. `fresh=True` lo vuelve a leer (para no pisar
        la nota u otros campos con datos viejos); `False` usa la última lectura si la hay."""
        if not fresh and auction_id in self._seen:
            return self._seen[auction_id]
        for a in self.client.my_auctions():
            if a["id"] == auction_id:
                self._seen[auction_id] = a
                return a
        raise WFMError("El contrato ya no existe en warframe.market (¿se cerró desde la web?)")

    def update(self, auction_id, price=None, visible=None, note=None):
        """Cambia precio, visibilidad y/o nota; lo que venga en None queda como está.
        (La API no permite cambiar los stats de un contrato ya publicado.)"""
        try:
            cur = self._current(auction_id)
            new = self.client.update_auction(
                auction_id,
                price=int(price) if price is not None else cur["buyout_price"],
                visible=bool(visible) if visible is not None else cur["visible"],
                note=note if note is not None else cur.get("note_raw", ""),
                minimal_reputation=cur.get("minimal_reputation", 0),
            )
        except (WFMError, requests.RequestException, ValueError) as e:
            return {"error": str(e)}
        self._seen[auction_id] = new
        with store.connect() as conn:
            store.log_event(conn, new, "update")
            store.add_price(conn, auction_id, new["buyout_price"], "manual")
        return {"auction": auction_view(new)}

    def price_history(self, auction_id):
        with store.connect() as conn:
            return {"history": store.price_history(conn, auction_id)}

    def repolarize(self, auction_id, polarity, price=None, visible=None, note=None):
        """La API no deja cambiar la polaridad de un contrato publicado: se publica uno igual con
        la polaridad nueva, se cierra el viejo (sin ensuciar el historial de cerrados) y el costo
        y el vínculo con el lote pasan al nuevo. Si falla la publicación, el viejo no se toca."""
        try:
            cur = self._current(auction_id)
            old = cur["item"]
            new = self.client.create_direct_sale(
                {
                    "weapon_url_name": old["weapon_url_name"],
                    "name": old.get("name", ""),
                    "attributes": [{"url_name": s["url_name"], "positive": bool(s["positive"]),
                                    "value": float(s["value"])} for s in old["attributes"]],
                    "mastery_level": int(old["mastery_level"]),
                    "mod_rank": int(old["mod_rank"]),
                    "re_rolls": int(old["re_rolls"]),
                    "polarity": polarity,
                },
                price=int(price) if price is not None else cur["buyout_price"],
                visible=bool(visible) if visible is not None else cur.get("visible", True),
                note=note if note is not None else cur.get("note_raw", ""),
            )
        except (WFMError, requests.RequestException, ValueError, KeyError) as e:
            return {"error": str(e)}
        self._seen[new["id"]] = new
        warning = None
        try:
            self.client.close_auction(auction_id)
            self._seen.pop(auction_id, None)
        except (WFMError, requests.RequestException) as e:
            warning = f"Se publicó la nueva pero no se pudo cerrar la vieja: {e}"
        with store.connect() as conn:
            store.log_event(conn, new, "create")
            store.sync_rivens(conn, [new])
            store.add_price(conn, new["id"], new["buyout_price"], "publish")
            if warning is None:
                conn.execute("UPDATE riven_costs SET auction_id = ? WHERE auction_id = ?", (new["id"], auction_id))
                conn.execute("UPDATE lot_openings SET auction_id = ? WHERE auction_id = ?", (new["id"], auction_id))
                conn.commit()
        return {"auction": auction_view(new), "replaced": None if warning else auction_id,
                "warning": warning, **self.local()}

    def create(self, item, price, visible=True, note="", cost=None, lot_id=None):
        """Publica una venta directa. `item` viene del formulario del modal. `cost` y `lot_id`
        (si el riven salió de un lote del stock unveiled) se guardan solo en local."""
        try:
            positives = [a for a in item["attributes"] if a["positive"]]
            negatives = [a for a in item["attributes"] if not a["positive"]]
            if not 2 <= len(positives) <= 3 or len(negatives) > 1:
                raise ValueError("Un riven tiene 2 o 3 stats positivos y como mucho 1 negativo")
            if not item.get("name", "").strip():
                raise ValueError("Falta el nombre del riven")
            if lot_id:
                with store.connect() as conn:
                    lot = store.get_lot(conn, int(lot_id))
                if not lot or lot["remaining"] <= 0:
                    raise ValueError("Ese lote ya no tiene rivens sin abrir")
            new = self.client.create_direct_sale(
                {
                    "weapon_url_name": item["weapon_url_name"],
                    "name": item["name"].strip(),
                    "attributes": [{"url_name": a["url_name"], "positive": bool(a["positive"]),
                                    "value": float(a["value"])} for a in item["attributes"]],
                    "mastery_level": int(item["mastery_level"]),
                    "mod_rank": int(item["mod_rank"]),
                    "re_rolls": int(item["re_rolls"]),
                    "polarity": item["polarity"],
                },
                price=int(price), visible=bool(visible), note=note or "",
            )
        except (WFMError, requests.RequestException, ValueError, KeyError) as e:
            return {"error": str(e)}
        self._seen[new["id"]] = new
        with store.connect() as conn:
            store.log_event(conn, new, "create")
            if lot_id:
                store.open_from_lot(conn, int(lot_id), new["id"])
            if cost not in (None, ""):
                store.set_cost(conn, new["id"], float(cost), int(lot_id) if lot_id else None)
        return {"auction": auction_view(new), **self.local()}

    def close(self, auction_id, sold_price=None):
        """Cierra el contrato y guarda una copia local (después desaparece de la API).
        La copia sale de la última lectura (un pedido menos): para el historial alcanza."""
        try:
            cur = self._current(auction_id, fresh=False)
            self.client.close_auction(auction_id)
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        self._seen.pop(auction_id, None)
        closed_at = store.now_iso()
        with store.connect() as conn:
            store.log_event(conn, {**cur, "closed": True}, "close",
                            sold_price=int(sold_price) if sold_price else None, at=closed_at)
        return {"closed": auction_id, "closed_at": closed_at}


def auction_view(a):
    """Lo que la interfaz necesita de un contrato."""
    item = a["item"]
    return {
        "id": a["id"],
        "price": a["buyout_price"],
        "visible": a.get("visible", True),
        "weapon": item["weapon_url_name"],
        "name": item.get("name", ""),
        "stats": [{"slug": s["url_name"], "value": s["value"], "positive": s["positive"]}
                  for s in item["attributes"]],
        "rolls": item.get("re_rolls"),
        "mr": item.get("mastery_level"),
        "rank": item.get("mod_rank"),
        "polarity": item.get("polarity"),
        "note": a.get("note_raw", ""),
        "updated": a.get("updated"),
    }


def set_window_icon():
    """pywebview en Windows no aplica el ícono a la ventana: se lo ponemos con Win32."""
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, TITLE)
    if not hwnd or not ICON.exists():
        return
    for size, which in ((16, 0), (32, 1)):  # ICON_SMALL, ICON_BIG
        hicon = user32.LoadImageW(None, str(ICON), 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
        user32.SendMessageW(hwnd, 0x80, which, hicon)  # WM_SETICON


def main():
    # Agrupa la ventana en la barra de tareas con su propio ícono, no el de Python.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("franh01.rivenstock")
    api = Api()
    api.start_counter()
    window = webview.create_window(
        TITLE, str(ROOT / "ui" / "index.html"), js_api=api,
        width=1180, height=780, min_size=(860, 580), background_color="#0c0518",
    )
    api._window = window
    window.events.shown += set_window_icon
    window.events.closing += api.on_closing
    webview.start()


if __name__ == "__main__":
    main()
