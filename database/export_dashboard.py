import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("database/content.db")
OUTPUT_PATH = Path("dashboard/data/dashboard_data.json")

FIELDS = [
    "content_id",
    "topic",
    "production_status",
    "publish_status",
    "analytics_status",
    "generator",
    "video_source",
    "artifact_id",
]


def normalize(value):
    if value is None or value == "":
        return "UNKNOWN"
    return value


def export_dashboard():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM videos ORDER BY content_id").fetchall()
    conn.close()

    videos = []
    for row in rows:
        item = {field: normalize(row[field]) for field in FIELDS}
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
