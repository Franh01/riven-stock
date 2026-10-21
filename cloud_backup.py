"""Copia de seguridad cifrada en la nube + conteo anónimo de instalaciones.

Un código de recuperación (128 bits al azar) que solo tiene el usuario da dos cosas: el id de la copia en el servidor
y la clave AES-GCM con que se cifra. El servidor guarda bytes opacos y no puede leer nada. Sin el código no hay forma
de recuperar la copia.
"""

import base64
import gzip
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import tempfile
import uuid
from pathlib import Path

import requests
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import store

URL = "https://botwmkn264es7nkbz7fk2o7asa0hezto.lambda-url.us-east-1.on.aws/"
MAGIC = b"RSB1"
TIMEOUT = 40
_B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


class CloudError(Exception):
    pass


def new_code():
    """Código tipo XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-X (26 letras base32 = 130 bits)."""
    raw = base64.b32encode(secrets.token_bytes(16)).decode().rstrip("=")
    return "-".join(raw[i:i + 5] for i in range(0, len(raw), 5))


def normalize(code):
    c = "".join(ch for ch in (code or "").upper() if ch in _B32)
    if len(c) != 26:
        raise CloudError("invalid_code")
    return c


def derive(code):
    """(id hex de 64, clave de 32 bytes) a partir del código."""
    k = normalize(code).encode()
    return (hmac.new(k, b"riven-stock/backup-id", hashlib.sha256).hexdigest(),
            hmac.new(k, b"riven-stock/backup-key", hashlib.sha256).digest())


def encrypt(plain, key):
    nonce = secrets.token_bytes(12)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, gzip.compress(plain), MAGIC)


def decrypt(blob, key):
    if blob[:4] != MAGIC:
        raise CloudError("invalid_backup")
    try:
        return gzip.decompress(AESGCM(key).decrypt(blob[4:16], blob[16:], MAGIC))
    except (InvalidTag, OSError):
        raise CloudError("bad_code")


def _post(body):
    try:
        r = requests.post(URL, json=body, timeout=TIMEOUT)
    except requests.RequestException:
        raise CloudError("cloud_offline")
    if r.status_code == 404:
        raise CloudError("no_cloud_backup")
    if not r.ok:
        raise CloudError("cloud_error")
    return r.json()


def _db_bytes():
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        store._copy_db(store.DB_PATH, tmp)
        return Path(tmp).read_bytes()
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def upload(code, version):
    cid, key = derive(code)
    blob = encrypt(_db_bytes(), key)
    r = _post({"op": "put", "id": cid, "blob": base64.b64encode(blob).decode(), "v": version})
    return {"at": r.get("at"), "size": len(blob)}


def download_to_file(code):
    """Baja y descifra la copia a un archivo temporal; devuelve su ruta (validada)."""
    cid, key = derive(code)
    r = _post({"op": "get", "id": cid})
    plain = decrypt(base64.b64decode(r["blob"]), key)
    fd, tmp = tempfile.mkstemp(suffix=".db")
    with os.fdopen(fd, "wb") as f:
        f.write(plain)
    if not store.validate_db(tmp):
        os.unlink(tmp)
        raise CloudError("invalid_backup")
    return tmp


def delete(code):
    cid, _ = derive(code)
    _post({"op": "del", "id": cid})


def install_id(conn):
    """UUID anónimo de esta instalación (no está ligado al código de recuperación)."""
    iid = store.settings(conn).get("install_id")
    if not iid:
        iid = str(uuid.uuid4())
        store.set_setting(conn, "install_id", iid)
    return iid


def ping(iid, version):
    _post({"op": "ping", "iid": iid, "v": version})


def stats():
    return _post({"op": "stats"})
