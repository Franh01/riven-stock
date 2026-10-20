"""Registro local (SQLite): lo que la app hace con los contratos, costos y stock unveiled.

- Un contrato cerrado desaparece de la API de warframe.market, así que acá se guarda una
  copia de cada contrato que se crea, edita o cierra (y si se vendió).
- El costo de cada riven y el stock de rivens unveiled son datos personales: nunca pasan
  por warframe.market.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "riven_stock.db"
RIVEN_TYPES = ("rifle", "shotgun", "pistol", "melee", "zaw", "kitgun")

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

-- Lotes de rivens unveiled comprados (ej. 6 melee por 50p).
CREATE TABLE IF NOT EXISTS stock_lots (
    id          INTEGER PRIMARY KEY,
    riven_type  TEXT NOT NULL,      -- rifle | shotgun | pistol | melee | zaw | kitgun
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    total_cost  REAL NOT NULL CHECK (total_cost >= 0),
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

-- Cada riven abierto de un lote: publicado (auction_id) o descartado (NULL).
CREATE TABLE IF NOT EXISTS lot_openings (
    id          INTEGER PRIMARY KEY,
    lot_id      INTEGER NOT NULL REFERENCES stock_lots (id),
    auction_id  TEXT,
    at          TEXT NOT NULL
);

-- Cuánto costó cada riven publicado. Si vino de un lote, lot_id lo indica (su costo ya
-- está contado en el total del lote, no se suma dos veces en "invertido").
CREATE TABLE IF NOT EXISTS riven_costs (
    auction_id  TEXT PRIMARY KEY,
    cost        REAL NOT NULL CHECK (cost >= 0),
    lot_id      INTEGER REFERENCES stock_lots (id),
    at          TEXT NOT NULL
);

-- Horas online efectivas acumuladas: UNA sola fila (id = 1), nunca una fila por muestra.
CREATE TABLE IF NOT EXISTS online_hours_log (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    seconds     REAL NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL
);

-- Horas online efectivas de cada riven publicado (una fila por riven, se actualiza en el lugar).
-- Los *_override en NULL usan el valor global.
CREATE TABLE IF NOT EXISTS riven_online_hours (
    auction_id      TEXT PRIMARY KEY,
    seconds         REAL NOT NULL DEFAULT 0,
    counting_since  TEXT NOT NULL,
    autodrop_on     INTEGER NOT NULL DEFAULT 1,
    hours_override  REAL,
    amount_override INTEGER,
    floor_override  INTEGER
);

-- Historial de precios: una fila por cambio de precio (source: seen, publish, manual, auto, revert).
CREATE TABLE IF NOT EXISTS price_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    auction_id  TEXT NOT NULL,
    price       INTEGER NOT NULL,
    source      TEXT NOT NULL,
    at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_price_history ON price_history (auction_id, at);

-- Bajas automáticas de precio (permiten el historial y la reversión).
CREATE TABLE IF NOT EXISTS price_drops (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    auction_id   TEXT NOT NULL,
    old_price    INTEGER NOT NULL,
    new_price    INTEGER NOT NULL,
    at           TEXT NOT NULL,
    reverted_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_price_drops ON price_drops (auction_id, at);

-- Avisos del panel de alertas.
CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    auction_id  TEXT,
    drop_id     INTEGER,
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    read_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_notifications ON notifications (read_at, created_at);

-- Preferencias de la interfaz (pywebview corre en modo privado: localStorage no persiste).
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL       -- JSON
);
"""


@contextmanager
def connect(path=DB_PATH):
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # la UI no espera al hilo de fondo
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(SCHEMA)
        _migrate(conn)
        yield conn
    finally:
        conn.close()


def _migrate(conn):
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(stock_lots)")}
    if "from_transmute" not in cols:
        conn.execute("ALTER TABLE stock_lots ADD COLUMN from_transmute INTEGER NOT NULL DEFAULT 0")
        conn.commit()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- Historial de contratos ------------------------------------------------

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


# ---- Costos ----------------------------------------------------------------

def set_cost(conn, auction_id, cost, lot_id=None):
    """Guarda (o borra, con cost=None) el costo de un riven."""
    if cost is None:
        conn.execute("DELETE FROM riven_costs WHERE auction_id = ? AND lot_id IS NULL", (auction_id,))
    else:
        conn.execute(
            """INSERT INTO riven_costs (auction_id, cost, lot_id, at) VALUES (?, ?, ?, ?)
               ON CONFLICT (auction_id) DO UPDATE SET cost = excluded.cost""",
            (auction_id, float(cost), lot_id, now_iso()),
        )
    conn.commit()


def costs(conn):
    """{auction_id: {"cost", "lot_id"}}"""
    return {r["auction_id"]: {"cost": r["cost"], "lot_id": r["lot_id"]}
            for r in conn.execute("SELECT auction_id, cost, lot_id FROM riven_costs")}


# ---- Stock unveiled ----------------------------------------------------------

def add_lot(conn, riven_type, quantity, total_cost, note="", from_transmute=False):
    """from_transmute: el costo viene de los rivens sacrificados, que ya cuentan en "invertido"."""
    cur = conn.execute(
        "INSERT INTO stock_lots (riven_type, quantity, total_cost, note, created_at, from_transmute) VALUES (?, ?, ?, ?, ?, ?)",
        (riven_type, int(quantity), float(total_cost), note or "", now_iso(), int(from_transmute)),
    )
    conn.commit()
    return cur.lastrowid


def lots(conn):
    """Lotes con cuántos quedan sin abrir, el más reciente primero."""
    rows = conn.execute(
        """SELECT l.*, COUNT(o.id) AS opened FROM stock_lots l
           LEFT JOIN lot_openings o ON o.lot_id = l.id
           GROUP BY l.id ORDER BY l.created_at DESC, l.id DESC"""
    ).fetchall()
    return [{**dict(r), "remaining": r["quantity"] - r["opened"], "unit_cost": r["total_cost"] / r["quantity"]}
            for r in rows]


def get_lot(conn, lot_id):
    return next((lot for lot in lots(conn) if lot["id"] == lot_id), None)


def open_from_lot(conn, lot_id, auction_id=None):
    """Descuenta un riven del lote: publicado (auction_id) o descartado (None)."""
    lot = get_lot(conn, lot_id)
    if not lot:
        raise ValueError("Ese lote no existe")
    if lot["remaining"] <= 0:
        raise ValueError("Ese lote ya no tiene rivens sin abrir")
    conn.execute("INSERT INTO lot_openings (lot_id, auction_id, at) VALUES (?, ?, ?)",
                 (lot_id, auction_id, now_iso()))
    conn.commit()


def delete_lot(conn, lot_id):
    """Solo se puede borrar un lote del que no se abrió ninguno (para corregir errores de carga)."""
    lot = get_lot(conn, lot_id)
    if lot and lot["opened"]:
        raise ValueError(f"Ya abriste {lot['opened']} de ese lote: no se puede borrar")
    conn.execute("DELETE FROM stock_lots WHERE id = ?", (lot_id,))
    conn.commit()


def invested(conn):
    """Platino invertido: el total de los lotes + el costo de los rivens comprados sueltos.
    Los lotes de transmutación no suman: su costo ya está en los rivens que se sacrificaron."""
    lots_total = conn.execute(
        "SELECT COALESCE(SUM(total_cost), 0) FROM stock_lots WHERE from_transmute = 0").fetchone()[0]
    loose = conn.execute("SELECT COALESCE(SUM(cost), 0) FROM riven_costs WHERE lot_id IS NULL").fetchone()[0]
    return lots_total + loose


# ---- Horas online efectivas ----------------------------------------------------

def add_online_seconds(conn, seconds):
    conn.execute(
        """INSERT INTO online_hours_log (id, seconds, updated_at) VALUES (1, ?, ?)
           ON CONFLICT (id) DO UPDATE SET seconds = seconds + excluded.seconds, updated_at = excluded.updated_at""",
        (float(seconds), now_iso()))
    conn.commit()


def online_seconds(conn):
    row = conn.execute("SELECT seconds FROM online_hours_log WHERE id = 1").fetchone()
    return row["seconds"] if row else 0.0


# ---- Horas por riven e historial de precios ---------------------------------------

def sync_rivens(conn, auctions):
    """Alinea riven_online_hours con los contratos abiertos: los nuevos empiezan en cero
    (con su primer precio en el historial) y los que ya no existen se borran."""
    ids = {a["id"] for a in auctions}
    known = {r["auction_id"] for r in conn.execute("SELECT auction_id FROM riven_online_hours")}
    now = now_iso()
    for a in auctions:
        if a["id"] not in known:
            conn.execute("INSERT INTO riven_online_hours (auction_id, counting_since) VALUES (?, ?)", (a["id"], now))
        last = last_price(conn, a["id"])
        if last is None:
            add_price(conn, a["id"], a["buyout_price"], "seen", commit=False)
    for gone in known - ids:
        conn.execute("DELETE FROM riven_online_hours WHERE auction_id = ?", (gone,))
    conn.commit()


def last_price(conn, auction_id):
    row = conn.execute("SELECT price FROM price_history WHERE auction_id = ? ORDER BY id DESC LIMIT 1",
                       (auction_id,)).fetchone()
    return row["price"] if row else None


def add_price(conn, auction_id, price, source, commit=True):
    """Registra el precio solo si cambió respecto del último guardado."""
    if last_price(conn, auction_id) == price:
        return
    conn.execute("INSERT INTO price_history (auction_id, price, source, at) VALUES (?, ?, ?, ?)",
                 (auction_id, int(price), source, now_iso()))
    if commit:
        conn.commit()


def price_history(conn, auction_id):
    return [dict(r) for r in conn.execute(
        "SELECT price, source, at FROM price_history WHERE auction_id = ? ORDER BY id", (auction_id,))]


def add_riven_seconds(conn, auction_ids, seconds):
    """Suma el tiempo efectivo a los rivens dados, en una sola sentencia."""
    ids = list(auction_ids)
    if not ids:
        return
    marks = ",".join("?" * len(ids))
    conn.execute(f"UPDATE riven_online_hours SET seconds = seconds + ? WHERE auction_id IN ({marks})",
                 [float(seconds), *ids])
    conn.commit()


def riven_hours(conn):
    return {r["auction_id"]: {"hours": r["seconds"] / 3600, "since": r["counting_since"],
                              "autodrop_on": bool(r["autodrop_on"]),
                              "hours_override": r["hours_override"], "amount_override": r["amount_override"],
                              "floor_override": r["floor_override"]}
            for r in conn.execute("SELECT * FROM riven_online_hours")}


def reset_riven_hours(conn, auction_id):
    conn.execute("UPDATE riven_online_hours SET seconds = 0, counting_since = ? WHERE auction_id = ?",
                 (now_iso(), auction_id))
    conn.commit()


def add_drop(conn, auction_id, old_price, new_price, text):
    """Registra una baja y su aviso en una sola transacción. Devuelve el id de la baja."""
    at = now_iso()
    cur = conn.execute("INSERT INTO price_drops (auction_id, old_price, new_price, at) VALUES (?, ?, ?, ?)",
                       (auction_id, old_price, new_price, at))
    conn.execute("INSERT INTO notifications (kind, auction_id, drop_id, text, created_at) VALUES ('drop', ?, ?, ?, ?)",
                 (auction_id, cur.lastrowid, text, at))
    conn.commit()
    return cur.lastrowid


def notifications(conn, limit=100):
    return [dict(r) for r in conn.execute(
        "SELECT n.*, d.old_price, d.new_price, d.reverted_at FROM notifications n "
        "LEFT JOIN price_drops d ON d.id = n.drop_id ORDER BY n.id DESC LIMIT ?", (limit,))]


def mark_read(conn, notification_id=None):
    q = "UPDATE notifications SET read_at = ? WHERE read_at IS NULL"
    if notification_id is None:
        conn.execute(q, (now_iso(),))
    else:
        conn.execute(q + " AND id = ?", (now_iso(), notification_id))
    conn.commit()


def get_drop(conn, drop_id):
    r = conn.execute("SELECT * FROM price_drops WHERE id = ?", (drop_id,)).fetchone()
    return dict(r) if r else None


def mark_reverted(conn, drop_id, auction_id):
    """Marca la baja como revertida, apaga el interruptor de ese riven y deja leídos sus avisos."""
    at = now_iso()
    conn.execute("UPDATE price_drops SET reverted_at = ? WHERE id = ?", (at, drop_id))
    conn.execute("UPDATE riven_online_hours SET autodrop_on = 0 WHERE auction_id = ?", (auction_id,))
    conn.execute("UPDATE notifications SET read_at = ? WHERE drop_id = ? AND read_at IS NULL", (at, drop_id))
    conn.commit()


def set_autodrop(conn, auction_id, on):
    conn.execute("UPDATE riven_online_hours SET autodrop_on = ? WHERE auction_id = ?", (1 if on else 0, auction_id))
    conn.commit()


# ---- Preferencias ------------------------------------------------------------

def settings(conn):
    return {r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT key, value FROM settings")}


def set_setting(conn, key, value):
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                 (key, json.dumps(value)))
    conn.commit()
