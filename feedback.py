"""Sugerencias y reportes de bugs: arma el envio a la nube (Lambda de feedback) con logs sanitizados."""
import base64
import gzip
import os
import re
import time

import requests

import store

URL = "https://zj5lrunnjlrusnzxmjzl75vtxu0lwjwx.lambda-url.us-east-1.on.aws/"
COOLDOWN_S = 10 * 60
MAX_LOG = 400 * 1024
MAX_SHOTS = 3
TIMEOUT = 40

_JWT = re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}")
_SECRET = re.compile(r"(?i)(JWT|token|authorization|bearer)(\s*[=:]\s*|\s+)[^\s\"',;]{8,}")
_USER = re.compile(r"(?i)([A-Z]:[\\/]+Users[\\/]+)[^\\/\s\"']+")
_CODE = re.compile(r"\b[A-Z0-9]{5}(?:-[A-Z0-9]{5}){4}(?:-[A-Z0-9]{1,5})?\b")


def sanitize(text):
    text = _JWT.sub("[token]", text)
    text = _SECRET.sub(lambda m: m.group(1) + m.group(2) + "[oculto]", text)
    text = _USER.sub(lambda m: m.group(1) + "usuario", text)
    return _CODE.sub("[codigo]", text)


def read_log(path):
    try:
        data = open(path, "rb").read()
    except OSError:
        return ""
    return sanitize(data[-MAX_LOG:].decode("utf-8", "replace"))


def wait_left(conn):
    last = float(store.settings(conn).get("feedback_last") or 0)
    return max(0, int(last + COOLDOWN_S - time.time()))


def send(conn, version, kind, text, contact, logs_text, shots):
    """Devuelve {ok:True} o {error:codigo, wait?:segundos}."""
    text = (text or "").strip()
    if kind not in ("suggestion", "bug"):
        return {"error": "bad_request"}
    if len(text) < 5:
        return {"error": "too_short"}
    left = wait_left(conn)
    if left:
        return {"error": "rate_limited", "wait": left}
    body = {"iid": _iid(conn), "v": version, "kind": kind, "text": text[:4000]}
    if (contact or "").strip():
        body["contact"] = contact.strip()[:120]
    if logs_text:
        body["logs"] = base64.b64encode(gzip.compress(logs_text.encode("utf-8"))).decode()
    shots = [s for s in (shots or []) if s.get("data")][:MAX_SHOTS]
    if shots:
        body["shots"] = [{"name": str(s.get("name", "captura"))[:60], "data": s["data"]} for s in shots]
    try:
        r = requests.post(URL, json=body, timeout=TIMEOUT)
    except requests.RequestException:
        return {"error": "network"}
    if r.status_code == 200:
        store.set_setting(conn, "feedback_last", time.time())
        return {"ok": True}
    if r.status_code == 429:
        try:
            w = int(r.json().get("retry_after") or COOLDOWN_S)
        except (ValueError, TypeError):
            w = COOLDOWN_S
        return {"error": "rate_limited", "wait": w}
    return {"error": "server"}


def send_crash(conn, version, files, log_path):
    """Envía el último crash pendiente con el log previo. Sin textos del usuario; todo sanitizado."""
    last = files[-1]
    try:
        text = sanitize(last.read_text(encoding="utf-8", errors="replace"))[:4000]
    except OSError:
        return {"ok": True}
    body = {"iid": _iid(conn), "v": version, "kind": "crash", "text": text or "crash"}
    logs = read_log(log_path)
    if logs:
        body["logs"] = base64.b64encode(gzip.compress(logs.encode("utf-8"))).decode()
    try:
        r = requests.post(URL, json=body, timeout=TIMEOUT)
    except requests.RequestException:
        return {"error": "network"}
    if r.status_code == 200 or r.status_code == 429:   # 429: ya se envió uno hace poco; no se acumula
        return {"ok": True}
    return {"error": "server"}


def _iid(conn):
    import cloud_backup
    return cloud_backup.install_id(conn)
