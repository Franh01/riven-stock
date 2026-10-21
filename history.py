"""Historial del mercado: guarda cada snapshot por arma e infiere ventas (para entrenar la estimación).

Una publicación que estaba en el snapshot anterior y ya no está se anota como probable venta, salvo que
parezca una republicación del mismo vendedor o que haya quedado fuera del corte de la búsqueda.
"""

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone

CUT = 480            # la búsqueda corta en ~500: con tantos resultados lo caro puede haber quedado afuera
ONLINE = ("ingame", "online")

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY, weapon TEXT NOT NULL, name TEXT, attrs TEXT NOT NULL, rolls INTEGER, mr INTEGER, rank INTEGER,
    seller TEXT, created TEXT, first_seen REAL NOT NULL, last_seen REAL NOT NULL,
    price_first INTEGER NOT NULL, price_last INTEGER NOT NULL, status_last TEXT, active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_listings_weapon ON listings(weapon, active);
CREATE TABLE IF NOT EXISTS snapshots (weapon TEXT NOT NULL, at REAL NOT NULL, n INTEGER NOT NULL, truncated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sales (
    id TEXT PRIMARY KEY, weapon TEXT NOT NULL, detected_at REAL NOT NULL, price INTEGER NOT NULL, price_first INTEGER,
    days_listed REAL, attrs TEXT NOT NULL, rolls INTEGER, mr INTEGER, rank INTEGER, seller TEXT,
    confidence TEXT NOT NULL, gap_h REAL
);
CREATE INDEX IF NOT EXISTS ix_sales_weapon ON sales(weapon, detected_at);
"""


@contextmanager
def _db(path):
    conn = sqlite3.connect(path, timeout=10)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _epoch(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def _sig(attrs):
    return tuple(sorted((a[0], bool(a[2])) for a in attrs))


def record(path, weapon, market, now=None):
    """Registra el snapshot (`market` = lista de `slim`) y devuelve cuántas ventas se infirieron."""
    now = now or time.time()
    cur = {a["id"]: a for a in market}
    truncated = len(market) >= CUT
    top = max((a["p"] for a in market), default=0)
    sold = 0
    with _db(path) as c:
        last = c.execute("SELECT MAX(at) FROM snapshots WHERE weapon=?", (weapon,)).fetchone()[0]
        gap_h = (now - last) / 3600 if last else None
        prev = {r["id"]: r for r in c.execute("SELECT * FROM listings WHERE weapon=? AND active=1", (weapon,))}
        cur_sigs = {}
        for a in market:
            cur_sigs.setdefault((a.get("nm"), _sig(a["s"])), a["id"])
        if last is not None:   # sin snapshot previo no hay con qué comparar
            for lid, r in prev.items():
                if lid in cur:
                    continue
                if truncated and r["price_last"] >= top:
                    continue   # pudo quedar fuera del corte, no sabemos si se vendió
                attrs = json.loads(r["attrs"])
                if (r["seller"], _sig(attrs)) in cur_sigs:
                    c.execute("UPDATE listings SET active=0 WHERE id=?", (lid,))   # republicada
                    continue
                if r["status_last"] in ONLINE and (gap_h or 0) <= 36:
                    conf = "alta"
                elif r["status_last"] in ONLINE or (gap_h or 0) <= 36:
                    conf = "media"
                else:
                    conf = "baja"
                created = _epoch(r["created"])
                days = (now - created) / 86400 if created else (now - r["first_seen"]) / 86400
                c.execute("INSERT OR IGNORE INTO sales VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (lid, weapon, now, r["price_last"], r["price_first"], round(days, 2), r["attrs"], r["rolls"],
                           r["mr"], r["rank"], r["seller"], conf, round(gap_h, 2) if gap_h else None))
                c.execute("UPDATE listings SET active=0 WHERE id=?", (lid,))
                sold += 1
        for lid, a in cur.items():
            if lid in prev:
                c.execute("UPDATE listings SET last_seen=?, price_last=?, status_last=? WHERE id=?", (now, a["p"], a.get("st"), lid))
            else:
                c.execute("INSERT OR REPLACE INTO listings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                          (lid, weapon, a.get("n"), json.dumps(a["s"]), a.get("r"), a.get("m"), a.get("k"), a.get("nm"), a.get("c"),
                           now, now, a["p"], a["p"], a.get("st")))
        c.execute("INSERT INTO snapshots VALUES (?,?,?,?)", (weapon, now, len(market), int(truncated)))
    return sold


def stats(path):
    """Resumen para mostrar cuánto se acumuló."""
    with _db(path) as c:
        q = lambda s: c.execute(s).fetchone()[0]
        return {"snapshots": q("SELECT COUNT(*) FROM snapshots"), "listings": q("SELECT COUNT(*) FROM listings"),
                "sales": q("SELECT COUNT(*) FROM sales"), "weapons": q("SELECT COUNT(DISTINCT weapon) FROM snapshots"),
                "since": q("SELECT MIN(at) FROM snapshots")}
