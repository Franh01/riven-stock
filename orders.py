"""Caché de órdenes por arma: se llena cuando la app está en idle, para no pedir todo de golpe."""

import json
import os
import threading
import time

from pricing import slim
from ratelimit import QUEUE

ONLINE = ("ingame", "online")


def cheapest_online(auctions, n=8):
    """Las `n` ventas directas más baratas de vendedores online (ingame u online)."""
    live = [
        a for a in auctions
        if a["owner"].get("status") in ONLINE
        and a.get("visible", True) and not a.get("closed") and not a.get("private")
    ]
    live.sort(key=lambda a: a["buyout_price"])
    return live[:n]


class OrderCache:
    IDLE_S = 30        # sin uso de la app durante este tiempo = idle
    TTL_S = 600        # pasado esto una entrada se vuelve a cargar
    PAUSE_S = 6        # descanso entre armas: la búsqueda de contratos admite ~10-20 pedidos por minuto (docs rules)
    BACKOFF_S = 10     # primera espera tras un error (429, red); se duplica en cada error seguido
    BACKOFF_MAX_S = 60  # tope: una ventana completa del límite por minuto

    def __init__(self, client, wanted_fn, path=None):
        self.client = client
        self.wanted_fn = wanted_fn      # () -> armas en orden de prioridad
        self._targeted = {}             # (arma, stats) -> (epoch, [slim]); consultas filtradas por stats
        self._data = {}                 # arma -> {"at": epoch, "orders": [contratos crudos]}
        self._lock = threading.Lock()
        self._active = time.monotonic()
        self._stop = threading.Event()
        self._fails = 0                 # errores seguidos de la carga de fondo
        self.path = path
        self._restore()

    def _restore(self):
        """Recupera el caché del disco (sobrevive a cerrar y abrir la app)."""
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._data = {k: v for k, v in data.items() if isinstance(v, dict) and "at" in v and "orders" in v}
        except Exception:
            self._data = {}

    def _persist(self):
        if not self.path:
            return
        try:
            with self._lock:
                blob = json.dumps(self._data)
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(blob)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def touch(self):
        self._active = time.monotonic()

    def idle(self):
        return time.monotonic() - self._active >= self.IDLE_S

    def get(self, weapon, max_age=None):
        with self._lock:
            e = self._data.get(weapon)
        if e and (max_age is None or time.time() - e["at"] <= max_age):
            return e
        return None

    def load(self, weapon):
        found = self.client.search_direct(weapon)
        market = [slim(a) for a in found
                  if a.get("visible", True) and not a.get("closed") and not a.get("private")]
        e = {"at": time.time(), "orders": cheapest_online(found), "market": market}
        with self._lock:
            self._data[weapon] = e
        self._persist()
        return e

    def targeted(self, weapon, stats):
        """Publicaciones del arma que tienen todos esos stats positivos (filtra el servidor, por eso
        no se pierden las caras: la búsqueda general corta en ~500 y se queda con las más baratas)."""
        key = (weapon, tuple(sorted(stats)))
        hit = self._targeted.get(key)
        if hit and time.time() - hit[0] <= self.TTL_S:
            return hit[1]
        found = self.client.search_direct(weapon, list(stats))
        rows = [slim(a) for a in found if a.get("visible", True) and not a.get("closed") and not a.get("private")]
        self._targeted[key] = (time.time(), rows)
        return rows

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(self.PAUSE_S):
            if not self.idle() or QUEUE.busy():   # nunca le roba turno a lo que pidió el usuario
                continue
            try:
                todo = [w for w in self.wanted_fn() if not self.get(w, self.TTL_S)]
                if todo:
                    self.load(todo[0])
                self._fails = 0
            except Exception:
                self._fails += 1                  # 429, sin red, etc.: esperar (creciente) y seguir
                self._stop.wait(min(self.BACKOFF_S * 2 ** (self._fails - 1), self.BACKOFF_MAX_S))
