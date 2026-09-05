import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("database/content.db")
SYNC_REPORT = Path("publish-sync/sync_report.json")

SYNC_MODE = "read_only"


def normalize_sql_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return None
    return value


def ensure_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id TEXT,
            postiz_id TEXT,
            publish_status TEXT,
            platforms TEXT,
            published_url TEXT,
            sync_mode TEXT,
            created_at TEXT
        )
        """
    )


def migrate():
    if not SYNC_REPORT.exists():
        raise FileNotFoundError(SYNC_REPORT)

    report = json.loads(SYNC_REPORT.read_text(encoding="utf-8"))

    with sqlite3.connect(DB_PATH) as conn:
        ensure_table(conn)

        for record in report.get("records", []):
            conn.execute(
                """
                INSERT INTO publish_status
                (content_id, postiz_id, publish_status, platforms,
                 published_url, sync_mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalize_sql_value(record.get("content_id")),
                    normalize_sql_value(record.get("postiz_id")),
                    normalize_sql_value(record.get("publish_status")),
                    normalize_sql_value(record.get("platforms")),
                    normalize_sql_value(record.get("published_url")),
                    SYNC_MODE,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        conn.commit()


if __name__ == "__main__":
    migrate()
