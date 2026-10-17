"""Riven Stock: app desktop (ventana pywebview + interfaz HTML en ui/)."""

import ctypes
import sys
from pathlib import Path

import requests
import webview

import store
from wfm_client import WFMClient, WFMError

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
ICON = ROOT / "assets" / "icon.ico"
TITLE = "Riven Stock"


class Api:
    """Métodos que la interfaz llama con window.pywebview.api.<método>()."""

    def __init__(self):
        self.client = WFMClient()

    def catalog(self):
        weapons = [
            {"slug": w["slug"], "name": w["i18n"]["en"]["name"], "type": w["rivenType"],
             "disposition": w.get("disposition")}
            for w in self.client.riven_weapons()
        ]
        stats = [
            {"slug": a["slug"], "name": a["i18n"]["en"]["name"], "unit": a.get("unit"),
             "positiveOnly": bool(a.get("positiveOnly")), "exclusiveTo": a.get("exclusiveTo") or []}
            for a in self.client.riven_attributes()
        ]
        return {
            "weapons": sorted(weapons, key=lambda w: w["name"]),
            "stats": sorted(stats, key=lambda s: s["name"]),
        }

    def search(self, weapon, positives, negatives):
        try:
            top = self.client.top_direct_ingame(weapon, positives, negatives or None)
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        return {"results": [
            {**auction_view(a), "seller": a["owner"]["ingame_name"],
             "reputation": a["owner"].get("reputation")}
            for a in top
        ]}

    # ---- Mis contratos ----------------------------------------------

    def my_auctions(self):
        try:
            auctions = [a for a in self.client.my_auctions() if a["is_direct_sell"]]
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        auctions.sort(key=lambda a: (not a["visible"], a["item"]["weapon_url_name"]))
        with store.connect() as conn:
            closed = store.closed_auctions(conn)
        return {
            "auctions": [auction_view(a) for a in auctions],
            "closed": [{**auction_view(c["auction"]), "sold_price": c["sold_price"],
                        "closed_at": c["closed_at"]} for c in closed],
        }

    def _current(self, auction_id):
        """El contrato tal como está ahora en la API (para no pisar campos con datos viejos)."""
        for a in self.client.my_auctions():
            if a["id"] == auction_id:
                return a
        raise WFMError("El contrato ya no existe en warframe.market (¿se cerró desde la web?)")

    def update(self, auction_id, price=None, visible=None):
        """Cambia precio y/o visibilidad; lo que venga en None queda como está."""
        try:
            cur = self._current(auction_id)
            new = self.client.update_auction(
                auction_id,
                price=int(price) if price is not None else cur["buyout_price"],
                visible=bool(visible) if visible is not None else cur["visible"],
                note=cur.get("note_raw", ""),
                minimal_reputation=cur.get("minimal_reputation", 0),
            )
        except (WFMError, requests.RequestException, ValueError) as e:
            return {"error": str(e)}
        with store.connect() as conn:
            store.log_event(conn, new, "update")
        return {"auction": auction_view(new)}

    def create(self, item, price, visible=True, note=""):
        """Publica una venta directa. `item` viene del formulario del modal."""
        try:
            positives = [a for a in item["attributes"] if a["positive"]]
            negatives = [a for a in item["attributes"] if not a["positive"]]
            if not 2 <= len(positives) <= 3 or len(negatives) > 1:
                raise ValueError("Un riven tiene 2 o 3 stats positivos y como mucho 1 negativo")
            if not item.get("name", "").strip():
                raise ValueError("Falta el nombre del riven")
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
        with store.connect() as conn:
            store.log_event(conn, new, "create")
        return {"auction": auction_view(new)}

    def close(self, auction_id, sold_price=None):
        """Cierra el contrato y guarda una copia local (después desaparece de la API)."""
        try:
            cur = self._current(auction_id)
            self.client.close_auction(auction_id)
        except (WFMError, requests.RequestException) as e:
            return {"error": str(e)}
        with store.connect() as conn:
            store.log_event(conn, {**cur, "closed": True}, "close",
                            sold_price=int(sold_price) if sold_price else None)
        return {"closed": auction_id}


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
