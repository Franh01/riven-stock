"""Diagnóstico de red para el log: entorno de la máquina y una sonda a warframe.market y a Cloudflare.

Se corre al arrancar y, como mucho una vez cada 5 minutos, cuando un pedido recibe 403/429/503 o se corta la
conexión. Solo escribe en el log (para que un reporte de bug traiga con qué red y qué respuesta de Cloudflare
se encontró la app); no cambia nada del comportamiento. La sonda va fuera de la cola de pedidos: es uno solo.
"""

import logging
import os
import platform
import socket
import ssl
import threading
import time
import urllib.request
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)

MIN_GAP_S = 300
_HOST = "api.warframe.market"
_lock = threading.Lock()
_last = 0.0


def _mask_ip(ip):
    """Oculta el final de la IP: alcanza para ver país y proveedor sin guardar la dirección completa."""
    if "." in ip:
        return ".".join(ip.split(".")[:2] + ["x", "x"])
    return ":".join(ip.split(":")[:3] + ["x"])


def _proxy_host(url):
    parts = urlsplit(url if "//" in url else "//" + url)
    return f"{parts.scheme or '?'}://{parts.hostname}:{parts.port}" if parts.hostname else "?"


def environment():
    """Una línea por dato: sistema, versiones de las librerías de red, zona horaria y proxies (sin credenciales)."""
    log.info("Entorno: %s, %s, Python %s %s", platform.platform(), platform.machine(), platform.python_version(),
             "(exe)" if getattr(__import__("sys"), "frozen", False) else "(fuentes)")
    log.info("Red: requests %s, urllib3 %s, %s, certifi %s", requests.__version__,
             getattr(requests.packages.urllib3, "__version__", "?"), ssl.OPENSSL_VERSION, _certifi())
    log.info("Hora local: %s (%s, UTC%+d)", time.strftime("%Y-%m-%d %H:%M:%S"), time.tzname[0], -time.timezone // 3600)
    try:
        proxies = {k: _proxy_host(v) for k, v in urllib.request.getproxies().items()}
    except Exception as e:
        proxies = f"error {e}"
    env = [k for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE")
           if os.environ.get(k) or os.environ.get(k.lower())]
    log.info("Proxies del sistema: %s; variables de entorno definidas: %s", proxies or "ninguno", env or "ninguna")


def _certifi():
    try:
        import certifi
        return certifi.__version__ if hasattr(certifi, "__version__") else "ok"
    except Exception:
        return "no"


def _probe_now(reason):
    log.info("Diagnóstico de red (%s)", reason)
    try:
        infos = socket.getaddrinfo(_HOST, 443, proto=socket.IPPROTO_TCP)
        log.info("DNS %s -> %s", _HOST, sorted({i[4][0] for i in infos}))
    except OSError as e:
        log.warning("DNS %s falló: %s", _HOST, e)
    from wfm_client import BASE_URL, HEADERS   # recién acá: wfm_client importa ratelimit, que importa este módulo
    for name, url, headers in (("warframe.market", BASE_URL + "/v2/versions", HEADERS),
                               ("cloudflare", "https://www.cloudflare.com/cdn-cgi/trace", {"User-Agent": HEADERS["User-Agent"]})):
        t0 = time.monotonic()
        try:
            r = requests.get(url, headers=headers, timeout=15)
        except requests.RequestException as e:
            log.warning("Sonda %s falló a los %d ms: %s: %s", name, (time.monotonic() - t0) * 1000, type(e).__name__, str(e)[:300])
            continue
        ms = (time.monotonic() - t0) * 1000
        heads = " ".join(f"{h}={r.headers.get(h)}" for h in ("server", "cf-ray", "cf-mitigated", "retry-after", "content-type") if r.headers.get(h))
        if name == "cloudflare" and r.ok:
            trace = dict(line.split("=", 1) for line in r.text.splitlines() if "=" in line)
            log.info("Sonda cloudflare 200 en %d ms: ip=%s loc=%s colo=%s http=%s tls=%s warp=%s gateway=%s",
                     ms, _mask_ip(trace.get("ip", "?")), trace.get("loc"), trace.get("colo"), trace.get("http"),
                     trace.get("tls"), trace.get("warp"), trace.get("gateway"))
            continue
        body = "" if r.ok else f" cuerpo={' '.join(r.text.split())[:300]!r}"
        log.log(logging.INFO if r.ok else logging.WARNING, "Sonda %s %s en %d ms: %s%s", name, r.status_code, ms, heads, body)
        date = r.headers.get("date")
        if name == "warframe.market" and date:
            try:
                skew = time.time() - parsedate_to_datetime(date).timestamp()
                log.log(logging.WARNING if abs(skew) > 120 else logging.INFO, "Reloj local vs servidor: %+.0f s", skew)
            except (TypeError, ValueError):
                pass


def probe(reason):
    """Lanza el diagnóstico en un hilo aparte, a lo sumo una vez cada MIN_GAP_S."""
    global _last
    with _lock:
        if time.monotonic() - _last < MIN_GAP_S and _last:
            return
        _last = time.monotonic()
    def run():
        try:
            _probe_now(reason)
        except Exception:
            log.exception("Falló el diagnóstico de red")
    threading.Thread(target=run, daemon=True, name="netdiag").start()
