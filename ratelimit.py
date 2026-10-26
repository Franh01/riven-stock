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
# Tope aparte para la búsqueda de contratos: Cloudflare (error 1015) frena con 11-14 búsquedas en un
# minuto (medido en el log del 23 al 26/10), aunque vayan de a una cada 6 s. Lo comparten todos los
# que buscan (recorrido de fondo, abrir un riven, Mercado), así que ninguna ráfaga se escapa.
SEARCH_LABEL = "get_rivens_by_weapon"
SEARCH_PER_MIN = 9
SEARCH_WINDOW_S = 60

_TRANSIENT = (requests.exceptions.Timeout, requests.exceptions.ConnectionError, socket.timeout,
              TimeoutError, ConnectionError, websocket.WebSocketException)


_LOG_HEADERS = ("server", "cf-ray", "cf-mitigated", "cf-cache-status", "retry-after", "content-type",
                "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "date")
STALL_S = 25          # un pedido en vuelo más de esto se registra como trabado


def _describe(res):
    """Resumen de una respuesta para el log: estado, tamaño, headers útiles para diagnosticar y, si falló, el cuerpo."""
    status = getattr(res, "status_code", None)
    if status is None:   # no es una respuesta HTTP (ej. el WebSocket)
        return type(res).__name__
    heads = " ".join(f"{h}={res.headers.get(h)}" for h in _LOG_HEADERS if res.headers.get(h))
    out = f"{status} {len(getattr(res, 'content', b'') or b'')}B {heads}"
    if status >= 300:
        body = " ".join((getattr(res, "text", "") or "").split())[:300]
        out += f" url={getattr(res, 'url', '')} cuerpo={body!r}"
    return out


class _Job:
    def __init__(self, fn, label):
        self.fn, self.label, self.tries = fn, label, 0
        self.t_submit = time.monotonic()
        self.event = threading.Event()
        self.result = self.error = None


class RequestQueue:
    def __init__(self, max_per_window=MAX_PER_WINDOW, window_s=WINDOW_S, clock=time.monotonic, sleep=time.sleep):
        self.max, self.window, self._clock, self._sleep = max_per_window, window_s, clock, sleep
        self._q = deque()
        self._cond = threading.Condition()
        self._stamps = deque()      # momentos en que arrancaron los últimos pedidos
        self._cooldown_until = 0.0
        self._search_stamps = deque()   # arranques de búsquedas de contratos en el último minuto
        self._pace_until = 0.0          # hasta cuándo espera una búsqueda por el tope por minuto
        self._reason = "limit"      # por qué espera la cola: limit (429) o net (sin conexión)
        self._active = None
        self._log = deque(maxlen=30)   # últimos pedidos que arrancaron (para mostrarlos en la UI)
        self._seq = 0
        self._total = self._done = 0   # lote actual: se reinicia cuando la cola se vacía
        self._inflight = None          # (job, momento en que salió) mientras el pedido está en la red
        threading.Thread(target=self._run, daemon=True, name="wfm-queue").start()
        threading.Thread(target=self._watch, daemon=True, name="wfm-queue-watch").start()

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

    def search_room(self):
        """Búsquedas de contratos que se pueden hacer ya sin pasar el tope por minuto."""
        with self._cond:
            self._trim_searches(self._clock())
            return SEARCH_PER_MIN - len(self._search_stamps)

    def _trim_searches(self, now):
        while self._search_stamps and self._search_stamps[0] <= now - SEARCH_WINDOW_S:
            self._search_stamps.popleft()

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
            pace = max(0.0, self._pace_until - now)
            reason = "pace" if pace > cooldown else self._reason
            cooldown = max(cooldown, pace)
            total = self._total
            return {
                "pending": waiting,
                "done": self._done,
                "total": total,
                "percent": round(100 * self._done / total) if total else 100,
                "eta_s": round(waiting * self.window / self.max + cooldown, 1),
                "cooldown_s": round(cooldown, 1),
                "reason": reason,
                "label": (self._active.label if self._active else (self._q[0].label if self._q else "")),
            }

    # ---- Hilo ejecutor ------------------------------------------------

    def _watch(self):
        """Registra pedidos trabados en la red o una cola que no avanza (no toca nada, solo deja rastro en el log)."""
        warned = {}
        while True:
            time.sleep(10)
            try:
                with self._cond:
                    inflight, depth, active = self._inflight, len(self._q), self._active
                    cooldown = max(0.0, self._cooldown_until - self._clock())
                if inflight:
                    job, since = inflight
                    age = time.monotonic() - since
                    if age > STALL_S and time.monotonic() - warned.get(id(job), 0) > 60:
                        warned[id(job)] = time.monotonic()
                        log.warning("Pedido trabado: %s lleva %.0f s sin respuesta (intento %d, %d en cola)",
                                    job.label, age, job.tries + 1, depth)
                elif active is not None and cooldown <= 0 and time.monotonic() - active.t_submit > 90                         and time.monotonic() - warned.get(id(active), 0) > 60:
                    warned[id(active)] = time.monotonic()
                    log.warning("La cola no avanza: %s espera hace %.0f s sin enfriamiento activo (%d en cola)",
                                active.label, time.monotonic() - active.t_submit, depth)
                if len(warned) > 200:
                    warned.clear()
            except Exception:
                log.exception("Falla en el vigilante de la cola")

    def _wait_slot(self, job=None):
        """Bloquea hasta que se pueda arrancar un pedido sin pasar el límite, y lo registra."""
        search = job is not None and job.label.startswith(SEARCH_LABEL)
        while True:
            now = self._clock()
            while self._stamps and self._stamps[0] <= now - self.window:
                self._stamps.popleft()
            wait = max(self._cooldown_until - now,
                       (self._stamps[0] + self.window - now) if len(self._stamps) >= self.max else 0.0)
            with self._cond:
                self._trim_searches(now)
                pace = (self._search_stamps[0] + SEARCH_WINDOW_S - now) if search and len(self._search_stamps) >= SEARCH_PER_MIN else 0.0
                self._pace_until = now + pace if pace > 0 else 0.0
            if pace > 0 and pace >= wait:
                log.info("Tope de %d búsquedas por minuto: %s espera %.0f s", SEARCH_PER_MIN, job.label, pace)
            wait = max(wait, pace)
            if wait <= 0:
                self._stamps.append(now)
                if search:
                    with self._cond:
                        self._search_stamps.append(now)
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
            self._wait_slot(job)
            with self._cond:
                self._seq += 1
                seq, depth = self._seq, len(self._q)
                self._log.append({"id": seq, "name": job.label, "retry": job.tries})
                t0 = time.monotonic()
                self._inflight = (job, t0)
            log.info("-> #%d %s (intento %d, esperó %.1f s en cola, %d detrás)", seq, job.label, job.tries + 1, t0 - job.t_submit, depth)
            try:
                res = job.fn()
            except _TRANSIENT as e:   # timeout o corte de red: se reintenta solo antes de mostrar nada
                self._inflight = None
                log.warning("xx #%d %s falló a los %d ms: %s: %s", seq, job.label, (time.monotonic() - t0) * 1000, type(e).__name__, str(e)[:300])
                _probe_later(f"{type(e).__name__} en {job.label}")
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
                self._inflight = None
                log.warning("xx #%d %s falló a los %d ms: %s: %s", seq, job.label, (time.monotonic() - t0) * 1000, type(e).__name__, str(e)[:300])
                self._finish(job, error=e)
                continue
            self._inflight = None
            status = getattr(res, "status_code", None)
            log.log(logging.WARNING if (status or 0) >= 400 else logging.INFO,
                    "<- #%d %s en %d ms: %s", seq, job.label, (time.monotonic() - t0) * 1000, _describe(res))
            if status in (403, 429, 503):
                _probe_later(f"{status} en {job.label}")
            if status == 429 and job.tries < MAX_RETRIES:
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


def _probe_later(reason):
    try:
        import netdiag
        netdiag.probe(reason)
    except Exception:
        log.exception("No se pudo lanzar el diagnóstico de red")


def _retry_after(res):
    try:
        return float(res.headers.get("Retry-After"))
    except (AttributeError, TypeError, ValueError):
        return None


QUEUE = RequestQueue()
