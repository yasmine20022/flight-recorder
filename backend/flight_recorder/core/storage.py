"""SQLite persistence for sessions and steps.

Schema (see CONTRACT.md):

    sessions(session_id PK, ticket_id, ticket_text, status, mode, created_at)
    steps(step_id PK, session_id FK, step_number, type, content JSON)

The full step payload is stored as JSON in ``steps.content`` so the structure can evolve
without migrations during the hackathon, while the columns we query on stay first-class.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from flight_recorder.config import settings
from flight_recorder.core.schemas import Session, SessionSummary, Step

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    ticket_id   TEXT NOT NULL,
    ticket_text TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'completed',
    mode        TEXT NOT NULL DEFAULT 'live',
    created_at  TEXT NOT NULL,
    synthetic   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS steps (
    step_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    step_number  INTEGER NOT NULL,
    type         TEXT NOT NULL,
    content      TEXT NOT NULL,
    UNIQUE(session_id, step_number)
);

CREATE INDEX IF NOT EXISTS idx_steps_session ON steps(session_id);
"""


class Storage:
    """Thin SQLite gateway. One instance per database file."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else settings.database_file
        self.init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            # Migrate older databases that predate the `synthetic` column.
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}
            if "synthetic" not in cols:
                conn.execute(
                    "ALTER TABLE sessions ADD COLUMN synthetic INTEGER NOT NULL DEFAULT 0"
                )

    # --- writes ---

    def save_session(self, session: Session) -> None:
        """Insert/replace a session and all of its steps."""
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO sessions
                   (session_id, ticket_id, ticket_text, status, mode, created_at, synthetic)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.session_id,
                    session.ticket_id,
                    session.ticket_text,
                    session.status.value,
                    session.mode.value,
                    session.created_at,
                    int(session.synthetic),
                ),
            )
            conn.execute("DELETE FROM steps WHERE session_id = ?", (session.session_id,))
            for step in session.steps:
                conn.execute(
                    """INSERT INTO steps (session_id, step_number, type, content)
                       VALUES (?, ?, ?, ?)""",
                    (
                        session.session_id,
                        step.step_number,
                        step.type.value,
                        step.model_dump_json(),
                    ),
                )

    def clear_all(self) -> None:
        """Delete every session and step (used to reset demo data)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM steps")
            conn.execute("DELETE FROM sessions")

    def append_step(self, session_id: str, step: Step) -> None:
        """Append a single step (used by the capture callback in Sprint 2)."""
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO steps (session_id, step_number, type, content)
                   VALUES (?, ?, ?, ?)""",
                (session_id, step.step_number, step.type.value, step.model_dump_json()),
            )

    # --- reads ---

    def list_sessions(self) -> list[SessionSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC"
            ).fetchall()
        return [SessionSummary(**dict(row)) for row in rows]

    def get_session(self, session_id: str) -> Optional[Session]:
        with self._connect() as conn:
            srow = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if srow is None:
                return None
            step_rows = conn.execute(
                "SELECT content FROM steps WHERE session_id = ? ORDER BY step_number",
                (session_id,),
            ).fetchall()
        steps = [Step(**json.loads(r["content"])) for r in step_rows]
        return Session(**dict(srow), steps=steps)


# Default instance used by the API.
storage = Storage()
