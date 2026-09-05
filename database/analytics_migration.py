import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("database/content.db")
REPORT_PATH = Path("analytics/analytics_report.json")


def normalize_sql_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if value is None:
        return None
    return value


def migrate_analytics():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id TEXT,
            platform TEXT,
            views INTEGER,
            clicks INTEGER,
            likes INTEGER,
            shares INTEGER,
            conversion INTEGER,
            sync_mode TEXT,
            created_at TEXT
        )
        """
    )

    if REPORT_PATH.exists():
        data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        for record in data.get("records", []):
            cursor.execute(
                """
                INSERT INTO analytics_metrics
                (content_id, platform, views, clicks, likes, shares, conversion, sync_mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalize_sql_value(record.get("content_id")),
                    normalize_sql_value(record.get("platform")),
                    record.get("views"),
                    record.get("clicks"),
                    record.get("likes"),
                    record.get("shares"),
                    record.get("conversion"),
                    "read_only",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    migrate_analytics()
