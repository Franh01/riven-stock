"""Cliente para la API de warframe.market (rivens, solo ventas directas).

Todas las llamadas a la API pasan por este módulo: si la API cambia, se
arregla acá. Rate limit: como máximo ~3 requests/segundo.
"""

import http.cookiejar
import json
import os
import threading
import time
from pathlib import Path

import requests
import websocket
from dotenv import load_dotenv

BASE_URL = "https://api.warframe.market"
CACHE_DIR = Path(__file__).parent / "cache"
CATALOG_MAX_AGE_HOURS = 24
MIN_INTERVAL_S = 0.35  # ~3 req/s
WS_URL = "wss://ws.warframe.market/socket"
# Estado del usuario (Invisible / Online / Online in game): va por WebSocket, no por REST.
STATUSES = ("invisible", "online", "ingame")
STATUS_MAX_SECONDS = 4 * 3600  # la web no deja más de 4 horas
SEARCH_CAP = 500  # la búsqueda de contratos corta en ~500 resultados (los más baratos con price_asc)

HEADERS = {
    "Platform": "pc",
    "Language": "en",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
}


class WFMError(Exception):
    pass


class AuthError(WFMError):
    """El JWT falta o expiró (401/403): copiar uno nuevo desde el navegador."""


class WFMClient:
    def __init__(self, jwt=None):
        load_dotenv(Path(__file__).parent / ".env")
        self.jwt = jwt if jwt is not None else (os.getenv("WFM_JWT") or "").strip() or None
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        # La API manda una cookie JWT anónima en cada respuesta; si la sesión la reenvía,
        # v1 la prefiere al header Authorization y responde 401. Auth va solo por header.
        self.session.cookies.set_policy(http.cookiejar.DefaultCookiePolicy(allowed_domains=[]))
        self._lock = threading.Lock()
        self._last_request = 0.0

    # ---- HTTP base ---------------------------------------------------

    def _throttle(self):
        with self._lock:
            wait = self._last_request + MIN_INTERVAL_S - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    def _request(self, method, path, *, auth=False, **kwargs):
        headers = kwargs.pop("headers", {})
        if auth:
            if not self.jwt:
                raise AuthError("Falta WFM_JWT en .env")
            # Verificado: v1 acepta "JWT <token>" (con "Bearer" da 401); v2 acepta "Bearer <token>".
            scheme = "JWT" if path.startswith("/v1/") else "Bearer"
            headers["Authorization"] = f"{scheme} {self.jwt}"
        for attempt in range(3):
            self._throttle()
            res = self.session.request(method, BASE_URL + path, headers=headers, timeout=20, **kwargs)
            if res.status_code == 429 and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            break
        if res.status_code in (401, 403) and auth:
            raise AuthError(f"{res.status_code} en {path}: el JWT no sirve o expiró")
        if res.status_code == 429:
            # Cloudflare (error 1015) bloquea un rato si hay muchas búsquedas seguidas.
            raise WFMError("warframe.market está limitando los pedidos (429). Esperá un minuto y probá de nuevo.")
        if not res.ok:
            raise WFMError(f"{method} {path} -> {res.status_code}: {res.text[:300]}")
        return res.json()

    def get(self, path, **kwargs):
        return self._request("GET", path, **kwargs)

    # ---- Catálogo (v2, cacheado) -------------------------------------

    def _cached(self, name, path):
        CACHE_DIR.mkdir(exist_ok=True)
        file = CACHE_DIR / f"{name}.json"
        if file.exists() and (time.time() - file.stat().st_mtime) / 3600 < CATALOG_MAX_AGE_HOURS:
            return json.loads(file.read_text(encoding="utf-8"))
        data = self.get(path)["data"]
        file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def riven_weapons(self):
        """~420 armas: slug (= weapon_url_name), i18n.en.name, group, disposition..."""
        return self._cached("riven_weapons", "/v2/riven/weapons")

    def riven_attributes(self):
        """~50 stats: slug (= nombre para positive_stats), positiveOnly, exclusiveTo..."""
        return self._cached("riven_attributes", "/v2/riven/attributes")

    # ---- Búsqueda de ventas directas (v1, sin auth) -------------------

    def search_direct(self, weapon, positive_stats=(), negative_stats=None):
        """Ventas directas de rivens de `weapon` con esos stats positivos.

        Filtra por stats del lado del servidor: la respuesta corta en ~500
        resultados, así que traer todo y filtrar local pierde vendedores.
        `negative_stats`: None = cualquiera; lista = esos negativos.
        """
        params = {
            "type": "riven",
            "weapon_url_name": weapon,
            "buyout_policy": "direct",
            "sort_by": "price_asc",
        }
        if positive_stats:
            params["positive_stats"] = ",".join(positive_stats)
        if negative_stats:
            params["negative_stats"] = ",".join(negative_stats)
        auctions = self.get("/v1/auctions/search", params=params)["payload"]["auctions"]
        return [a for a in auctions if a.get("is_direct_sell")]

    def top_direct_ingame(self, weapon, positive_stats=(), negative_stats=None, n=7):
        """Las `n` ventas directas más baratas de vendedores `ingame`."""
        return cheapest_ingame(self.search_direct(weapon, positive_stats, negative_stats), n)

    # ---- Cuenta propia (requiere JWT) ---------------------------------

    # ---- Estado del usuario (WebSocket v2) ------------------------------
    # Verificado el 2026-10-17: se autentica con el mensaje @wfm|cmd/auth/signIn {"token"} (no
    # sirven ni el header ni la cookie). Después del signIn el servidor manda solo el estado actual
    # (@wfm|event/status/set con status, statusUntil, statusSetAt).

    def _ws_session(self, command=None, timeout=10):
        """Abre el socket, se autentica y (opcional) manda `command` = (route, payload).
        Devuelve {"status": <último @wfm|event/status/set>, "reply": <respuesta al comando>}."""
        if not self.jwt:
            raise AuthError("Falta WFM_JWT en .env")
        self._throttle()
        ws = websocket.create_connection(WS_URL, timeout=timeout, origin="https://warframe.market",
                                         header=[f"User-Agent: {HEADERS['User-Agent']}"])
        try:
            ws.send(json.dumps({"route": "@wfm|cmd/auth/signIn", "payload": {"token": self.jwt}, "id": "auth"}))
            status = reply = None
            sent = False
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                ws.settimeout(max(0.1, deadline - time.monotonic()))
                try:
                    msg = json.loads(ws.recv())
                except websocket.WebSocketTimeoutException:
                    break
                route = msg.get("route", "")
                if msg.get("id") == "auth":
                    if not route.endswith(":ok"):
                        raise AuthError(f"warframe.market rechazó el token en el WebSocket ({msg.get('payload')})")
                    if command and not sent:
                        ws.send(json.dumps({"route": command[0], "payload": command[1], "id": "cmd"}))
                        sent = True
                elif route == "@wfm|event/status/set":
                    status = msg.get("payload")
                elif msg.get("id") == "cmd":
                    reply = msg
                    deadline = min(deadline, time.monotonic() + 1.5)  # el evento con statusUntil llega enseguida
                elif route == "@wfm|protect/error":
                    raise WFMError(f"WebSocket: {msg.get('payload')}")
                # Listo cuando hay estado y, si había comando, su respuesta + el evento posterior.
                if status and (not command or (reply and status.get("statusSetAt", "") >= reply.get("payload", {}).get("statusSetAt", ""))):
                    break
            return {"status": status, "reply": reply}
        finally:
            ws.close()

    def get_status(self):
        """{"status", "statusUntil", "statusSetAt"} del usuario dueño del JWT."""
        st = self._ws_session(timeout=8)["status"]
        if not st:
            raise WFMError("warframe.market no mandó el estado")
        return st

    def set_status(self, status, duration_s=STATUS_MAX_SECONDS):
        """Cambia el estado por `duration_s` segundos (máximo 4 h). Acción visible para todos."""
        if status not in STATUSES:
            raise ValueError(f"Estado inválido: {status}")
        duration_s = max(60, min(int(duration_s), STATUS_MAX_SECONDS))
        res = self._ws_session(("@wfm|cmd/status/set", {"status": status, "duration": duration_s}))
        reply = res["reply"]
        if not reply:
            raise WFMError("warframe.market no respondió al cambio de estado")
        if not reply.get("route", "").endswith(":ok"):
            raise WFMError(f"No se pudo cambiar el estado: {reply.get('payload')}")
        st = res["status"] or {}
        if st.get("status") != status:   # el evento llegó antes que el ok: armar con la respuesta
            st = {**reply.get("payload", {}), "statusUntil": st.get("statusUntil")}
        return st

    def me(self):
        """Datos del usuario dueño del JWT (v2)."""
        return self.get("/v2/me", auth=True)["data"]

    def my_auctions(self):
        """Contratos propios (v1, con auth), incluidos los ocultos. Los cerrados no aparecen."""
        return self.get("/v1/profile/auctions", auth=True)["payload"]["auctions"]

    # ---- Escritura (endpoints sacados de los HAR de la web) -----------
    # Son acciones públicas en la cuenta del usuario: la app pide confirmación antes.

    def update_auction(self, auction_id, *, price, visible, note="", minimal_reputation=0):
        """Edita precio / visibilidad / nota. La web manda siempre todos los campos.
        `note` es texto plano (usar `note_raw` del contrato, no `note`, que viene en HTML)."""
        body = {
            "starting_price": price,
            "buyout_price": price,
            "minimal_reputation": minimal_reputation,
            "visible": visible,
            "note": note,
        }
        return self._request("PUT", f"/v1/auctions/entry/{auction_id}", auth=True, json=body)[
            "payload"]["auction"]

    def create_direct_sale(self, item, *, price, visible=True, note="", minimal_reputation=0):
        """Publica una venta directa. `item`: type, weapon_url_name, name, attributes
        [{url_name, positive, value}], mastery_level, mod_rank, re_rolls, polarity."""
        body = {
            "starting_price": price,
            "buyout_price": price,
            "minimal_reputation": minimal_reputation,
            "visible": visible,
            "note": note,
            "item": {"type": "riven", **item},
        }
        return self._request("POST", "/v1/auctions/create", auth=True, json=body)["payload"]["auction"]

    def close_auction(self, auction_id):
        """Cierra el contrato. Después de esto desaparece de la API: guardarlo antes localmente."""
        return self._request("PUT", f"/v1/auctions/entry/{auction_id}/close", auth=True)[
            "payload"]["auction_id"]

    def profile_auctions(self, slug):
        """Contratos públicos de un perfil (v1, no necesita auth)."""
        return self.get(f"/v1/profile/{slug}/auctions")["payload"]["auctions"]


def cheapest_ingame(auctions, n=7):
    """Las `n` más baratas de vendedores `ingame` dentro de una búsqueda."""
    ingame = [
        a for a in auctions
        if a["owner"].get("status") == "ingame"
        and a.get("visible", True) and not a.get("closed") and not a.get("private")
    ]
    ingame.sort(key=lambda a: a["buyout_price"])
    return ingame[:n]


def summarize(auction):
    """Una línea legible de un contrato."""
    item = auction["item"]
    stats = ", ".join(
        f"{'+' if a['positive'] else '-'}{a['url_name']} {a['value']}" for a in item["attributes"]
    )
    line = (
        f"{auction['buyout_price']:>6}p  {item['weapon_url_name']} {item.get('name', '')}"
        f"  [{stats}]  rolls={item.get('re_rolls')}  MR{item.get('mastery_level')}"
    )
    # En la búsqueda `owner` es un objeto; en los contratos de un perfil es solo el id.
    owner = auction["owner"]
    if isinstance(owner, dict):
        line += f"  {owner['ingame_name']} ({owner['status']}, rep {owner.get('reputation')})"
    return line
