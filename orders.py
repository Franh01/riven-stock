"""Caché de órdenes por arma: se llena cuando la app está en idle, para no pedir todo de golpe."""

import threading
import time

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
    PAUSE_S = 3        # descanso entre armas (además del _throttle del cliente)
    BACKOFF_S = 60     # espera tras un error (429, red)

    def __init__(self, client, wanted_fn):
        self.client = client
        self.wanted_fn = wanted_fn      # () -> armas en orden de prioridad
        self._data = {}                 # arma -> {"at": epoch, "orders": [contratos crudos]}
        self._lock = threading.Lock()
        self._active = time.monotonic()
        self._stop = threading.Event()

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
        e = {"at": time.time(), "orders": cheapest_online(found)}
        with self._lock:
            self._data[weapon] = e
        return e

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(self.PAUSE_S):
            if not self.idle():
                continue
            try:
                todo = [w for w in self.wanted_fn() if not self.get(w, self.TTL_S)]
                if todo:
                    self.load(todo[0])
            except Exception:
                self._stop.wait(self.BACKOFF_S)   # 429, sin red, etc.: esperar y seguir
