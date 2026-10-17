"""Riven Stock: app desktop (ventana pywebview + interfaz HTML en ui/)."""

import ctypes
import sys
from pathlib import Path

import requests
import webview

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
            {
                "id": a["id"],
                "price": a["buyout_price"],
                "name": a["item"].get("name", ""),
                "stats": [{"slug": s["url_name"], "value": s["value"], "positive": s["positive"]}
                          for s in a["item"]["attributes"]],
                "rolls": a["item"].get("re_rolls"),
                "mr": a["item"].get("mastery_level"),
                "seller": a["owner"]["ingame_name"],
                "reputation": a["owner"].get("reputation"),
            }
            for a in top
        ]}


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
