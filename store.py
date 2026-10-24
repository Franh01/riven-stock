"""Registro local (SQLite): lo que la app hace con los contratos, costos y stock unveiled.

- Un contrato cerrado desaparece de la API de warframe.market, así que acá se guarda una
  copia de cada contrato que se crea, edita o cierra (y si se vendió).
- El costo de cada riven y el stock de rivens unveiled son datos personales: nunca pasan
  por warframe.market.
"""

import json
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

LEGACY_DB = Path(__file__).parent / "riven_stock.db"   # ubicación vieja: dentro de la carpeta de la app


def _data_dir():
    """Carpeta de datos del usuario, fuera de la instalación: reinstalar o actualizar no la toca."""
    env = os.environ.get("RIVEN_STOCK_DATA")
    if env:
        return Path(env)
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home()) / "RivenStock"


DATA_DIR = _data_dir()
DB_PATH = DATA_DIR / "riven_stock.db"
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_KEEP = 10
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

-- Foto diaria del mercado por arma (tendencias).
CREATE TABLE IF NOT EXISTS market_snapshots (
    weapon      TEXT NOT NULL,
    day         TEXT NOT NULL,      -- YYYY-MM-DD (UTC)
    n_orders    INTEGER NOT NULL,
    n_online    INTEGER NOT NULL,
    min_price   INTEGER,
    median      INTEGER,
    PRIMARY KEY (weapon, day)
);

-- Preferencias de la interfaz (pywebview corre en modo privado: localStorage no persiste).
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL       -- JSON
);
"""


def _copy_db(src, dst):
    """Copia consistente de una base SQLite (incluye lo que esté en el WAL)."""
    a = sqlite3.connect(src)
    b = sqlite3.connect(dst)
    try:
        a.backup(b)
    finally:
        b.close()
        a.close()


def migrate_legacy():
    """Primera vez con la carpeta nueva: copia la base de la ubicación vieja (la vieja queda como respaldo)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists() or not LEGACY_DB.exists():
        return False
    _copy_db(LEGACY_DB, DB_PATH)
    return True


def make_backup(path=DB_PATH, tag=""):
    """Copia fechada en backups/, dejando solo las últimas BACKUP_KEEP. Devuelve la ruta o None."""
    if not Path(path).exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"riven_stock-{datetime.now().strftime('%Y%m%d-%H%M%S')}{tag}.db"
    _copy_db(path, dest)
    for old in sorted(BACKUP_DIR.glob("riven_stock-*.db"))[:-BACKUP_KEEP]:
        try:
            old.unlink()
        except OSError:
            pass
    return dest


def list_backups():
    if not BACKUP_DIR.exists():
        return []
    return [{"name": p.name, "path": str(p), "size": p.stat().st_size, "at": p.stat().st_mtime}
            for p in sorted(BACKUP_DIR.glob("riven_stock-*.db"), reverse=True)]


def backup_if_due(hours=24):
    """Backup automático si el último tiene más de `hours` horas (y hay datos). Devuelve la ruta o None."""
    last = list_backups()
    if last and datetime.now().timestamp() - last[0]["at"] < hours * 3600:
        return None
    return make_backup()


def validate_db(path):
    """True si `path` es una base de Riven Stock legible."""
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            if c.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                return False
            tablas = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return "auction_events" in tablas
        finally:
            c.close()
    except sqlite3.Error:
        return False


def restore_db(src):
    """Reemplaza el contenido de la base actual por el de `src`. Antes deja un backup de seguridad."""
    make_backup(tag="-antes-de-restaurar")
    a = sqlite3.connect(src)
    b = sqlite3.connect(DB_PATH)
    try:
        a.backup(b)
    finally:
        b.close()
        a.close()


@contextmanager
def connect(path=DB_PATH):
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # la UI no espera al hilo de fondo
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(SCHEMA)
        _migrate(conn, path)
        yield conn
    finally:
        conn.close()


def _m1_from_transmute(conn):
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(stock_lots)")}
    if "from_transmute" not in cols:
        conn.execute("ALTER TABLE stock_lots ADD COLUMN from_transmute INTEGER NOT NULL DEFAULT 0")


# Migraciones en orden: la posición + 1 es la versión del esquema (PRAGMA user_version).
# Solo se agregan al final, nunca se reordenan ni se editan las ya publicadas.
def _m2_sale_hours(conn):
    # Horas online efectivas que llevaba cada riven al venderse (la fila de riven_online_hours se borra al cerrar).
    conn.execute("""CREATE TABLE IF NOT EXISTS sale_hours (
        auction_id TEXT PRIMARY KEY,
        hours      REAL NOT NULL,
        at         TEXT NOT NULL
    )""")


MIGRATIONS = [_m1_from_transmute, _m2_sale_hours]


def _migrate(conn, path=DB_PATH):
    actual = conn.execute("PRAGMA user_version").fetchone()[0]
    if actual >= len(MIGRATIONS):
        return
    if actual > 0 and str(path) != ":memory:":
        # Backup previo: solo si ya había datos con un esquema anterior.
        try:
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(FULL)")
            shutil.copy2(path, f"{path}.pre-v{actual}.bak")
        except OSError:
            pass
    for i in range(actual, len(MIGRATIONS)):
        MIGRATIONS[i](conn)
        conn.execute(f"PRAGMA user_version = {i + 1}")
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


def log_sale_hours(conn, auction_id, hours, at=None):
    conn.execute("INSERT OR REPLACE INTO sale_hours (auction_id, hours, at) VALUES (?, ?, ?)",
                 (auction_id, float(hours), at or now_iso()))
    conn.commit()


def sale_hours(conn):
    return {r["auction_id"]: r["hours"] for r in conn.execute("SELECT auction_id, hours FROM sale_hours")}


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


def assign_lot(conn, auction_id, lot_id, cost=None):
    """Le asigna un lote de origen a un riven ya publicado que no tenía (se olvidó al crearlo).
    El costo pasa a contar dentro del lote (cost=None: el costo unitario del lote)."""
    if conn.execute("SELECT 1 FROM lot_openings WHERE auction_id = ?", (auction_id,)).fetchone():
        raise ValueError("Ese riven ya tiene un origen")
    lot = get_lot(conn, lot_id)
    open_from_lot(conn, lot_id, auction_id)
    conn.execute(
        """INSERT INTO riven_costs (auction_id, cost, lot_id, at) VALUES (?, ?, ?, ?)
           ON CONFLICT (auction_id) DO UPDATE SET cost = excluded.cost, lot_id = excluded.lot_id""",
        (auction_id, float(lot["unit_cost"] if cost is None else cost), lot_id, now_iso()))
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

def sync_rivens(conn, auctions, prune=True):
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
    if prune:   # con una lista parcial (ej. un solo contrato nuevo) NO se poda: borraria los ajustes de los demas
        for gone in known - ids:
            conn.execute("DELETE FROM riven_online_hours WHERE auction_id = ?", (gone,))
    conn.commit()


def migrate_auction(conn, old_id, new_id):
    """Al editar un riven la publicación nueva reemplaza a la vieja: le pasa sus horas, interruptor y
    ajustes propios, historial de precios y avisos, para que todo siga apuntando a un contrato vivo."""
    row = conn.execute("SELECT * FROM riven_online_hours WHERE auction_id = ?", (old_id,)).fetchone()
    if row:
        conn.execute("UPDATE riven_online_hours SET seconds = ?, counting_since = ?, autodrop_on = ?, "
                     "hours_override = ?, amount_override = ?, floor_override = ? WHERE auction_id = ?",
                     (row["seconds"], row["counting_since"], row["autodrop_on"], row["hours_override"],
                      row["amount_override"], row["floor_override"], new_id))
        conn.execute("DELETE FROM riven_online_hours WHERE auction_id = ?", (old_id,))
    for table in ("price_history", "price_drops", "notifications"):
        conn.execute(f"UPDATE {table} SET auction_id = ? WHERE auction_id = ?", (new_id, old_id))
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


def add_opportunity(conn, auction_id, text):
    """Aviso de oportunidad; devuelve False si esa publicación ya se avisó."""
    if conn.execute("SELECT 1 FROM notifications WHERE kind = 'opp' AND auction_id = ?", (auction_id,)).fetchone():
        return False
    conn.execute("INSERT INTO notifications (kind, auction_id, text, created_at) VALUES ('opp', ?, ?, ?)",
                 (auction_id, text, now_iso()))
    conn.commit()
    return True


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


def delete_read(conn):
    """Borra los avisos ya leídos. Devuelve cuántos."""
    n = conn.execute("DELETE FROM notifications WHERE read_at IS NOT NULL").rowcount
    conn.commit()
    return n


def delete_notifications(conn, ids):
    ids = [int(i) for i in ids]
    if ids:
        conn.execute(f"DELETE FROM notifications WHERE id IN ({','.join('?' * len(ids))})", ids)
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


def set_overrides(conn, auction_id, hours, amount, floor):
    """Ajustes propios de un riven; None = usa el valor global."""
    conn.execute("UPDATE riven_online_hours SET hours_override = ?, amount_override = ?, floor_override = ? WHERE auction_id = ?",
                 (hours, amount, floor, auction_id))
    conn.commit()


def purge_old(conn):
    """Retención: avisos leídos de más de 60 días y bajas de más de 12 meses."""
    conn.execute("DELETE FROM notifications WHERE read_at IS NOT NULL AND created_at < datetime('now', '-60 days')")
    conn.execute("DELETE FROM price_drops WHERE at < datetime('now', '-12 months') "
                 "AND id NOT IN (SELECT drop_id FROM notifications WHERE drop_id IS NOT NULL)")
    conn.commit()
    conn.execute("DELETE FROM market_snapshots WHERE day < date('now', '-24 months')")
    conn.commit()


def save_snapshot(conn, weapon, market):
    """Guarda (o pisa) la foto de hoy: cantidad, mínimo y mediana de las ventas directas."""
    prices = sorted(a["p"] for a in market)
    online = [a["p"] for a in market if a.get("st") in ("ingame", "online")]
    conn.execute(
        "INSERT OR REPLACE INTO market_snapshots (weapon, day, n_orders, n_online, min_price, median) "
        "VALUES (?, date('now'), ?, ?, ?, ?)",
        (weapon, len(prices), len(online), prices[0] if prices else None,
         prices[len(prices) // 2] if prices else None))
    conn.commit()


def snapshot_done_today(conn, weapon):
    return conn.execute("SELECT 1 FROM market_snapshots WHERE weapon = ? AND day = date('now')", (weapon,)).fetchone() is not None


def market_trend(conn, weapon, days=90):
    return [dict(r) for r in conn.execute(
        "SELECT day, n_orders, n_online, min_price, median FROM market_snapshots "
        "WHERE weapon = ? AND day >= date('now', ?) ORDER BY day", (weapon, f"-{int(days)} days"))]


# ---- Preferencias ------------------------------------------------------------

def settings(conn):
    return {r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT key, value FROM settings")}


def set_setting(conn, key, value):
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                 (key, json.dumps(value)))
    conn.commit()
