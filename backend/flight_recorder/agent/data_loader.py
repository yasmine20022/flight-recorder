"""Loads the simulated back-office data the tools read from.

- KB articles and user directory come from JSON files.
- Past tickets live in a dedicated SQLite database (separate from the trace DB),
  seeded once from ``tickets_seed.json``.

Everything here is data-driven: the tools never hard-code an answer, they look it up.
"""
from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path

from flight_recorder.config import BACKEND_DIR

DATA_DIR = BACKEND_DIR / "data"
KB_FILE = DATA_DIR / "kb_articles.json"
USERS_FILE = DATA_DIR / "users.json"
TICKETS_SEED_FILE = DATA_DIR / "tickets_seed.json"
TICKETS_DB = DATA_DIR / "tickets.db"


@lru_cache(maxsize=1)
def load_kb() -> list[dict]:
    return json.loads(KB_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_users() -> list[dict]:
    return json.loads(USERS_FILE.read_text(encoding="utf-8"))


def ensure_tickets_db(db_path: Path | None = None) -> Path:
    """Create and seed the past-tickets database if it is missing/empty. Idempotent."""
    path = Path(db_path) if db_path else TICKETS_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS past_tickets (
                   ticket_id             TEXT PRIMARY KEY,
                   category              TEXT NOT NULL,
                   summary               TEXT NOT NULL,
                   priority              TEXT NOT NULL,
                   status                TEXT NOT NULL DEFAULT 'Resolved',
                   created_at            TEXT NOT NULL DEFAULT '',
                   resolver              TEXT NOT NULL DEFAULT '',
                   resolution            TEXT NOT NULL,
                   resolution_time_hours REAL NOT NULL DEFAULT 0
               )"""
        )
        (count,) = conn.execute("SELECT COUNT(*) FROM past_tickets").fetchone()
        if count == 0:
            seed = json.loads(TICKETS_SEED_FILE.read_text(encoding="utf-8"))
            conn.executemany(
                """INSERT INTO past_tickets
                   (ticket_id, category, summary, priority, status, created_at,
                    resolver, resolution, resolution_time_hours)
                   VALUES (:ticket_id, :category, :summary, :priority, :status,
                           :created_at, :resolver, :resolution, :resolution_time_hours)""",
                seed,
            )
        conn.commit()
    finally:
        conn.close()
    return path
