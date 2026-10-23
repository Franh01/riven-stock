"""Cola central de pedidos a warframe.market.

Todo lo que sale hacia la API (REST y el WebSocket) pasa por `QUEUE.submit`. Una sola cola FIFO
y un solo hilo que ejecuta los pedidos de a uno, así que nunca hay dos en vuelo, y una ventana
deslizante garantiza que en cualquier ventana de `window_s` segundos no arranquen más de
`max_per_window` pedidos. Si hace falta esperar, se espera: quien llamó se queda bloqueado y la
UI muestra el avance con `status()`.

Si la API contesta 429, la cola entera se frena (enfriamiento con espera creciente, o el
Retry-After del servidor) y ese mismo pedido se reintenta primero, sin perder su lugar.
"""

import logging
import socket
import threading
import time
from collections import deque

import requests
import websocket

log = logging.getLogger(__name__)

MAX_PER_WINDOW = 3
WINDOW_S = 1.1        # 3 pedidos por 1.1 s (~2.7/s): margen para el jitter de red
MAX_RETRIES = 3       # reintentos ante 429 antes de rendirse
COOLDOWN_S = 10       # primera espera tras un 429; se duplica en cada reintento
COOLDOWN_MAX_S = 60
NET_RETRIES = 3       # reintentos ante timeouts o cortes de red antes de mostrar el error
NET_WAIT_S = 3        # espera base; se duplica en cada reintento

_TRANSIENT = (requests.exceptions.Timeout, requests.exceptions.ConnectionError, socket.timeout,
              TimeoutError, ConnectionError, websocket.WebSocketException)


class _Job:
    def __init__(self, fn, label):
        self.fn, self.label, self.tries = fn, label, 0
        self.event = threading.Event()
        self.result = self.error = None


class RequestQueue:
    def __init__(self, max_per_window=MAX_PER_WINDOW, window_s=WINDOW_S, clock=time.monotonic, sleep=time.sleep):
        self.max, self.window, self._clock, self._sleep = max_per_window, window_s, clock, sleep
        self._q = deque()
        self._cond = threading.Condition()
        self._stamps = deque()      # momentos en que arrancaron los últimos pedidos
        self._cooldown_until = 0.0
        self._reason = "limit"      # por qué espera la cola: limit (429) o net (sin conexión)
        self._active = None
        self._log = deque(maxlen=30)   # últimos pedidos que arrancaron (para mostrarlos en la UI)
        self._seq = 0
        self._total = self._done = 0   # lote actual: se reinicia cuando la cola se vacía
        threading.Thread(target=self._run, daemon=True, name="wfm-queue").start()

    # ---- API para quien pide ------------------------------------------

    def submit(self, fn, label=""):
        """Encola `fn` (que hace el pedido y devuelve su respuesta) y espera su resultado."""
        job = _Job(fn, label)
        with self._cond:
            self._q.append(job)
            self._total += 1
            self._cond.notify()
        job.event.wait()
        if job.error is not None:
            raise job.error
        return job.result

    def recent(self, since=0):
        """Pedidos que arrancaron después de `since` (id), del más viejo al más nuevo."""
        with self._cond:
            return [dict(e) for e in self._log if e["id"] > since]

    def busy(self):
        """True si hay pedidos esperando o en curso (el cargador de fondo no debe meterse)."""
        with self._cond:
            return bool(self._q) or self._active is not None

    def status(self):
        """Foto para la UI: cuántos faltan, porcentaje del lote y tiempo estimado."""
        with self._cond:
            waiting = len(self._q) + (1 if self._active else 0)
            now = self._clock()
            cooldown = max(0.0, self._cooldown_until - now)
            total = self._total
            return {
                "pending": waiting,
                "done": self._done,
                "total": total,
                "percent": round(100 * self._done / total) if total else 100,
                "eta_s": round(waiting * self.window / self.max + cooldown, 1),
                "cooldown_s": round(cooldown, 1),
                "reason": self._reason,
                "label": (self._active.label if self._active else (self._q[0].label if self._q else "")),
            }

    # ---- Hilo ejecutor ------------------------------------------------

    def _wait_slot(self):
        """Bloquea hasta que se pueda arrancar un pedido sin pasar el límite, y lo registra."""
        while True:
            now = self._clock()
            while self._stamps and self._stamps[0] <= now - self.window:
                self._stamps.popleft()
            wait = max(self._cooldown_until - now,
                       (self._stamps[0] + self.window - now) if len(self._stamps) >= self.max else 0.0)
            if wait <= 0:
                self._stamps.append(now)
                return
            self._sleep(wait)

    def _finish(self, job, result=None, error=None):
        job.result, job.error = result, error
        with self._cond:
            self._active = None
            self._done += 1
            if not self._q:
                self._total = self._done = 0
        job.event.set()

    def _run(self):
        # Si algo inesperado rompe una vuelta, se registra y el hilo sigue: si moría, todo pedido quedaba colgado para siempre.
        while True:
            try:
                self._loop()
            except BaseException:
                log.exception("Falla inesperada en la cola de pedidos; se reinicia el hilo")
                with self._cond:
                    job, self._active = self._active, None
                if job is not None:
                    self._finish(job, error=RuntimeError("falla interna de la cola de pedidos"))
                time.sleep(1)

    def _loop(self):
        while True:
            with self._cond:
                while not self._q:
                    self._cond.wait()
                job = self._q.popleft()
                self._active = job
            self._wait_slot()
            with self._cond:
                self._seq += 1
                self._log.append({"id": self._seq, "name": job.label, "retry": job.tries})
            try:
                res = job.fn()
            except _TRANSIENT as e:   # timeout o corte de red: se reintenta solo antes de mostrar nada
                if job.tries < NET_RETRIES:
                    self._cooldown_until = self._clock() + NET_WAIT_S * (2 ** job.tries)
                    self._reason = "net"
                    log.info("Sin respuesta en %s (%s): reintento %d de %d", job.label, type(e).__name__, job.tries + 1, NET_RETRIES)
                    job.tries += 1
                    with self._cond:
                        self._q.appendleft(job)
                        self._active = None
                    continue
                self._finish(job, error=e)
                continue
            except Exception as e:   # el error le llega a quien pidió
                self._finish(job, error=e)
                continue
            if getattr(res, "status_code", None) == 429 and job.tries < MAX_RETRIES:
                retry_after = _retry_after(res)
                wait = retry_after if retry_after is not None else COOLDOWN_S * (2 ** job.tries)
                self._cooldown_until = self._clock() + min(wait, COOLDOWN_MAX_S)
                self._reason = "limit"
                log.info("429 en %s: espera %.0f s (reintento %d de %d)", job.label, min(wait, COOLDOWN_MAX_S), job.tries + 1, MAX_RETRIES)
                job.tries += 1
                with self._cond:
                    self._q.appendleft(job)   # conserva su lugar: sigue siendo el primero
                    self._active = None
                continue
            self._finish(job, result=res)


def _retry_after(res):
    try:
        return float(res.headers.get("Retry-After"))
    except (AttributeError, TypeError, ValueError):
        return None


QUEUE = RequestQueue()
