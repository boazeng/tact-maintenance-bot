"""
SQLite storage base — shared connection + generic key/JSON-blob helpers.

Every domain table stores a primary key column plus a `data` TEXT column that
holds the full record as a JSON object. This mirrors the DynamoDB backend's
behaviour (records are schemaless dicts) so the engine code round-trips
identically regardless of backend.

DB file location resolves from the BOT_DB_PATH env var, else <repo>/data/takt-bots.db.
"""

import os
import json
import sqlite3
import logging
import threading

logger = logging.getLogger("taktbots.sqlite")

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DEFAULT_DB = os.path.join(_REPO_ROOT, "data", "takt-bots.db")

_local = threading.local()
_initialized = False
_init_lock = threading.Lock()

# table -> primary key column
_TABLES = {
    "bot_scripts": "script_id",
    "sessions": "phone",
    "service_calls": "id",
    "messages": "id",
    "bot_prompts": "prompt_id",
    "bot_test_scenarios": "scenario_id",
}


def _db_path():
    return os.environ.get("BOT_DB_PATH", _DEFAULT_DB)


def get_conn():
    """Return a thread-local SQLite connection, creating the schema on first use."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        path = _db_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
        _ensure_schema(conn)
    return conn


def _ensure_schema(conn):
    global _initialized
    with _init_lock:
        for table, pk in _TABLES.items():
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {table} "
                f"({pk} TEXT PRIMARY KEY, data TEXT NOT NULL)"
            )
        conn.commit()
        _initialized = True


# ── Generic record helpers ────────────────────────────────────

def put(table, pk_value, data):
    """Insert or replace a full record (data dict) keyed by pk_value."""
    pk = _TABLES[table]
    conn = get_conn()
    conn.execute(
        f"INSERT OR REPLACE INTO {table} ({pk}, data) VALUES (?, ?)",
        (pk_value, json.dumps(data, ensure_ascii=False)),
    )
    conn.commit()


def get(table, pk_value):
    """Return the record dict for pk_value, or None."""
    pk = _TABLES[table]
    conn = get_conn()
    row = conn.execute(
        f"SELECT data FROM {table} WHERE {pk} = ?", (pk_value,)
    ).fetchone()
    if row:
        return json.loads(row["data"])
    return None


def list_all(table):
    """Return all record dicts in the table."""
    conn = get_conn()
    rows = conn.execute(f"SELECT data FROM {table}").fetchall()
    return [json.loads(r["data"]) for r in rows]


def delete(table, pk_value):
    """Delete a record by primary key."""
    pk = _TABLES[table]
    conn = get_conn()
    conn.execute(f"DELETE FROM {table} WHERE {pk} = ?", (pk_value,))
    conn.commit()
