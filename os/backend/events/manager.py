from data.database_path import database_path
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = database_path()


class EventManager:
    """Lightweight event registry for OS-level workflow coordination.

    This layer intentionally does not replace existing managers. It records
    lifecycle events so future orchestration can consume them.
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self._ensure_table()

    def _ensure_table(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    entity_type TEXT,
                    entity_id TEXT,
                    payload TEXT,
                    created_at TEXT NOT NULL,
                    processed INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()

    def emit(
        self,
        event_type,
        source,
        entity_type=None,
        entity_id=None,
        payload=None,
    ):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO events
                (event_type, source, entity_type, entity_id, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    source,
                    entity_type,
                    entity_id,
                    json.dumps(payload or {}),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def list_events(self, limit=100):
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return rows
