"""Registro local (SQLite) de lo que la app hace con los contratos.

Un contrato cerrado desaparece de la API de warframe.market, así que acá se
guarda una copia de cada contrato que se crea, edita o cierra (y si se vendió).
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "riven_stock.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS auction_events (
    id          INTEGER PRIMARY KEY,
    auction_id  TEXT NOT NULL,
    action      TEXT NOT NULL CHECK (action IN ('create', 'update', 'close')),
    sold_price  INTEGER,            -- solo en 'close', si se vendió
    snapshot    TEXT NOT NULL,      -- JSON del contrato como estaba (o quedó)
    at          TEXT NOT NULL       -- ISO 8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_events_auction ON auction_events (auction_id);
"""


@contextmanager
def connect(path=DB_PATH):
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        yield conn
    finally:
        conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_event(conn, auction, action, sold_price=None, at=None):
    conn.execute(
        "INSERT INTO auction_events (auction_id, action, sold_price, snapshot, at) VALUES (?, ?, ?, ?, ?)",
        (auction["id"], action, sold_price, json.dumps(auction, ensure_ascii=False), at or now_iso()),
    )
    conn.commit()


def closed_auctions(conn):
    """Contratos cerrados desde la app, el más reciente primero."""
    rows = conn.execute(
        "SELECT auction_id, sold_price, snapshot, at FROM auction_events WHERE action = 'close' ORDER BY at DESC"
    ).fetchall()
    return [{"auction": json.loads(r["snapshot"]), "sold_price": r["sold_price"], "closed_at": r["at"]}
            for r in rows]
