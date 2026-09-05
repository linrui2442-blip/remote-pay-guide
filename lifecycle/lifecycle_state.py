import json
import sqlite3
from pathlib import Path

DB_PATH = Path("database/content.db")
OUTPUT_PATH = Path("lifecycle/lifecycle_report.json")

STATES = [
    "CREATED",
    "SCRIPT_READY",
    "VIDEO_GENERATED",
    "QUALITY_CHECKED",
    "READY_TO_PUBLISH",
    "PUBLISHED",
    "ANALYTICS_TRACKING",
    "COMPLETED",
    "FAILED",
]


def normalize(value):
    return "UNKNOWN" if value in (None, "") else value


def calculate_state(production_status, publish_status, analytics_exists):
    if production_status in ("failed", "FAILED"):
        return "FAILED"
    if analytics_exists:
        return "ANALYTICS_TRACKING"
    if publish_status in ("published", "PUBLISHED"):
        return "PUBLISHED"
    if production_status:
        return "VIDEO_GENERATED"
    return "CREATED"


def build_report():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    publish_exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='publish_status'").fetchone()
    analytics_exists_table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_metrics'").fetchone()

    publish_rows = {}
    if publish_exists:
        for row in conn.execute("SELECT * FROM publish_status"):
            publish_rows[row["content_id"]] = row

    analytics_ids = set()
    if analytics_exists_table:
        analytics_ids = {row["content_id"] for row in conn.execute("SELECT content_id FROM analytics_metrics")}

    records = []
    for row in conn.execute("SELECT * FROM videos ORDER BY content_id"):
        content_id = row["content_id"]
        publish = publish_rows.get(content_id)
        publish_value = normalize(publish["publish_status"] if publish else None)
        production_value = normalize(row["production_status"])
        records.append({
            "content_id": content_id,
            "current_state": calculate_state(production_value, publish_value, content_id in analytics_ids),
            "production_status": production_value,
            "publish_status": publish_value,
            "analytics_status": "TRACKING" if content_id in analytics_ids else "UNKNOWN"
        })

    conn.close()

    OUTPUT_PATH.write_text(json.dumps({"sync_mode": "read_only", "records": records}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build_report()
