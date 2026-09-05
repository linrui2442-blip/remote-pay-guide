import json
import sqlite3
from pathlib import Path

REGISTRY_PATH = Path("content-registry/registry.json")
DB_PATH = Path("database/content.db")
REPORT_PATH = Path("database/migration_report.json")


def value_or_unknown(value):
    return value if value not in (None, "") else "UNKNOWN"


def migrate():
    records = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        content_id TEXT PRIMARY KEY,
        topic TEXT,
        category TEXT,
        script_source TEXT,
        video_source TEXT,
        generator TEXT,
        video_file TEXT,
        artifact_id TEXT,
        production_status TEXT,
        publish_status TEXT,
        platforms TEXT,
        postiz_id TEXT,
        published_url TEXT,
        analytics_status TEXT
    )
    """)

    imported = 0
    skipped = 0
    failed = 0

    for item in records:
        try:
            cur.execute("""
            INSERT OR REPLACE INTO videos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                value_or_unknown(item.get("content_id")),
                value_or_unknown(item.get("topic")),
                value_or_unknown(item.get("category")),
                value_or_unknown(item.get("script_source")),
                value_or_unknown(item.get("video_source")),
                value_or_unknown(item.get("generator")),
                value_or_unknown(item.get("video_file")),
                value_or_unknown(item.get("artifact_id")),
                value_or_unknown(item.get("production_status")),
                value_or_unknown(item.get("publish_status")),
                json.dumps(item.get("platforms", {})),
                value_or_unknown(item.get("postiz_id")),
                value_or_unknown(item.get("published_url")),
                value_or_unknown(item.get("analytics_status")),
            ))
            imported += 1
        except Exception:
            failed += 1

    conn.commit()
    conn.close()

    REPORT_PATH.write_text(json.dumps({
        "imported_records": imported,
        "skipped_records": skipped,
        "failed_records": failed
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    migrate()
