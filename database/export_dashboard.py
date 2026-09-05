import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("database/content.db")
OUTPUT_PATH = Path("dashboard/data/dashboard_data.json")

BASE_FIELDS = [
    "content_id",
    "topic",
    "production_status",
    "publish_status",
    "analytics_status",
    "generator",
    "video_source",
    "artifact_id",
]

PUBLISH_FIELDS = [
    "postiz_id",
    "platforms",
    "published_url",
]


def normalize(value):
    if value is None or value == "":
        return "UNKNOWN"
    return value


def export_dashboard():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    publish_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='publish_status'"
    ).fetchone()

    publish_rows = {}
    if publish_exists:
        rows = conn.execute("SELECT * FROM publish_status").fetchall()
        publish_rows = {row["content_id"]: row for row in rows}

    rows = conn.execute("SELECT * FROM videos ORDER BY content_id").fetchall()
    conn.close()

    videos = []
    for row in rows:
        item = {field: normalize(row[field]) for field in BASE_FIELDS}
        publish = publish_rows.get(row["content_id"])
        if publish:
            item.update({field: normalize(publish[field]) for field in PUBLISH_FIELDS})
        else:
            item.update({field: "UNKNOWN" for field in PUBLISH_FIELDS})
        videos.append(item)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_videos": len(videos),
                "videos": videos,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    export_dashboard()
