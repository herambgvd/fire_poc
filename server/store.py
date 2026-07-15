"""SQLite event store for the web POC.

One table, ``events`` — a confirmed fire/smoke detection with its snapshot and
evidence-clip paths. Kept deliberately tiny; the real product (vizor_ai_fire)
will use the vizor platform's Postgres + storage layer.

Every call opens its own short-lived connection, so it is safe to call from the
pipeline worker thread and from FastAPI request threads at the same time.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import APP_DIR

DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "fire_poc.db"
SNAPSHOT_DIR = DATA_DIR / "snapshots"


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the events table + on-disk dirs if they don't exist yet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ts            TEXT    NOT NULL,   -- ISO-8601 UTC
                camera        TEXT    NOT NULL,
                type          TEXT    NOT NULL,   -- 'Fire' | 'Smoke'
                confidence    REAL,               -- best stage-2 box conf
                stage1        REAL,               -- stage-1 screening prob
                stage2        REAL,               -- stage-2 confirm conf
                snapshot      TEXT,               -- relative snapshot filename
                evidence      TEXT                -- absolute evidence mp4 path
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")


def add_event(*, camera: str, type: str, confidence: float | None,
              stage1: float | None, stage2: float | None,
              snapshot: str | None, evidence: str | None,
              ts: str | None = None) -> int:
    """Insert one confirmed detection; returns its new row id."""
    ts = ts or datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO events (ts, camera, type, confidence, stage1, stage2, snapshot, evidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ts, camera, type, confidence, stage1, stage2, snapshot, evidence),
        )
        return int(cur.lastrowid)


def _row_to_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["has_snapshot"] = bool(d.get("snapshot"))
    d["has_evidence"] = bool(d.get("evidence"))
    return d


def list_events(*, type: str | None = None, date: str | None = None,
                page: int = 1, page_size: int = 25) -> dict:
    """Paginated, optionally filtered events (newest first).

    ``date`` is a YYYY-MM-DD prefix match on the (UTC) timestamp.
    Returns {items, total, page, page_size}.
    """
    where, params = [], []
    if type:
        where.append("type = ?")
        params.append(type)
    if date:
        where.append("ts LIKE ?")
        params.append(f"{date}%")
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    page = max(1, int(page))
    page_size = min(200, max(1, int(page_size)))
    offset = (page - 1) * page_size

    with _conn() as c:
        total = c.execute(f"SELECT COUNT(*) FROM events {clause}", params).fetchone()[0]
        rows = c.execute(
            f"SELECT * FROM events {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, page_size, offset),
        ).fetchall()
    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


def get_event(event_id: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return _row_to_dict(r) if r else None


def counts_today() -> dict:
    """Totals for the dashboard: today + all-time + by type."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        today_n = c.execute(
            "SELECT COUNT(*) FROM events WHERE ts LIKE ?", (f"{today}%",)
        ).fetchone()[0]
        fire = c.execute("SELECT COUNT(*) FROM events WHERE type = 'Fire'").fetchone()[0]
        smoke = c.execute("SELECT COUNT(*) FROM events WHERE type = 'Smoke'").fetchone()[0]
        last = c.execute("SELECT * FROM events ORDER BY id DESC LIMIT 1").fetchone()
    return {
        "total": int(total),
        "today": int(today_n),
        "fire": int(fire),
        "smoke": int(smoke),
        "last_event": _row_to_dict(last) if last else None,
    }


def all_events() -> list[dict]:
    """Every event, newest first — used for CSV export."""
    with _conn() as c:
        rows = c.execute("SELECT * FROM events ORDER BY id DESC").fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_event(event_id: int) -> dict | None:
    """Delete one event row; returns the deleted row (so its files can be removed)."""
    e = get_event(event_id)
    if not e:
        return None
    with _conn() as c:
        c.execute("DELETE FROM events WHERE id = ?", (event_id,))
    return e


def clear_events() -> list[dict]:
    """Delete ALL events; returns the removed rows (for file cleanup)."""
    rows = all_events()
    with _conn() as c:
        c.execute("DELETE FROM events")
    return rows
