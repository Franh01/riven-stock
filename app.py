"""Riven Stock: app desktop (ventana pywebview + interfaz HTML en ui/)."""

import ctypes
import json
import sys
from pathlib import Path

import requests
import webview

import store
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

    def catalog(self):
        weapons = [
            {"slug": w["slug"], "name": w["i18n"]["en"]["name"], "type": w["rivenType"],
             "disposition": w.get("disposition")}
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
        return {"auction": auction_view(new)}

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
    window = webview.create_window(
        TITLE, str(ROOT / "ui" / "index.html"), js_api=Api(),
        width=1180, height=780, min_size=(860, 580), background_color="#0c0518",
    )
    window.events.shown += set_window_icon
    webview.start()


if __name__ == "__main__":
    main()
