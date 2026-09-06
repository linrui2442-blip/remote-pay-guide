import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("database/content.db")

DEFAULT_PLATFORMS = [
    {
        "platform_name": "youtube",
        "publish_supported": 1,
        "analytics_supported": 1,
        "oauth_required": 1,
        "metric_types": ["views", "watch_time", "retention"],
    },
    {
        "platform_name": "instagram",
        "publish_supported": 1,
        "analytics_supported": 0,
        "oauth_required": 1,
        "metric_types": [],
    },
    {
        "platform_name": "facebook",
        "publish_supported": 1,
        "analytics_supported": 0,
        "oauth_required": 1,
        "metric_types": [],
    },
    {
        "platform_name": "tiktok",
        "publish_supported": 1,
        "analytics_supported": 0,
        "oauth_required": 1,
        "metric_types": [],
    },
]


def migrate():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS platform_capabilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform_name TEXT UNIQUE,
                publish_supported INTEGER,
                analytics_supported INTEGER,
                oauth_required INTEGER,
                metric_types TEXT,
                created_at TEXT
            )
            """
        )

        for platform in DEFAULT_PLATFORMS:
            conn.execute(
                """
                INSERT OR IGNORE INTO platform_capabilities
                (platform_name, publish_supported, analytics_supported,
                 oauth_required, metric_types, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    platform["platform_name"],
                    platform["publish_supported"],
                    platform["analytics_supported"],
                    platform["oauth_required"],
                    json.dumps(platform["metric_types"]),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        conn.commit()


if __name__ == "__main__":
    migrate()
