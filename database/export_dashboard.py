import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("database/content.db")
OUTPUT_PATH = Path("dashboard/data/dashboard_data.json")
LIFECYCLE_PATH = Path("lifecycle/lifecycle_report.json")
HEALTH_PATH = Path("health/health_report.json")

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

PUBLISH_FIELDS = ["postiz_id", "platforms", "published_url"]
ANALYTICS_FIELDS = ["platform", "views", "clicks", "likes", "shares", "conversion"]

STRING_FIELDS = {
    "content_id",
    "topic",
    "production_status",
    "publish_status",
    "analytics_status",
    "generator",
    "video_source",
    "artifact_id",
    "postiz_id",
    "platforms",
    "published_url",
    "platform",
}


def normalize(value, field=None):
    if value is None or value == "":
        return "UNKNOWN" if field in STRING_FIELDS else value
    return value


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def export_dashboard():
    lifecycle_data = load_json(LIFECYCLE_PATH, {"records": []})
    lifecycle_rows = {item.get("content_id"): item for item in lifecycle_data.get("records", [])}

    health_data = load_json(HEALTH_PATH, {"system_status": "UNKNOWN", "checks": []})

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    publish_rows = {}
    if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='publish_status'").fetchone():
        publish_rows = {row["content_id"]: row for row in conn.execute("SELECT * FROM publish_status")}

    analytics_rows = {}
    if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_metrics'").fetchone():
        analytics_rows = {row["content_id"]: row for row in conn.execute("SELECT * FROM analytics_metrics")}

    rows = conn.execute("SELECT * FROM videos ORDER BY content_id").fetchall()
    conn.close()

    videos = []
    for row in rows:
        item = {field: normalize(row[field], field) for field in BASE_FIELDS}

        publish = publish_rows.get(row["content_id"])
        item.update({field: normalize(publish[field], field) if publish else "UNKNOWN" for field in PUBLISH_FIELDS})

        analytics = analytics_rows.get(row["content_id"])
        item["analytics"] = {
            field: normalize(analytics[field], field) if analytics else ("UNKNOWN" if field == "platform" else 0)
            for field in ANALYTICS_FIELDS
        }

        lifecycle = lifecycle_rows.get(row["content_id"], {})
        item["lifecycle"] = {
            "current_state": normalize(lifecycle.get("current_state"), "current_state")
        }

        videos.append(item)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_videos": len(videos),
        "system_health": {
            "system_status": normalize(health_data.get("system_status"), "system_status"),
            "checks": health_data.get("checks", [])
        },
        "videos": videos,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    export_dashboard()
