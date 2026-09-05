import json
import sqlite3
from pathlib import Path

REGISTRY_PATH = Path("content-registry/registry.json")
DB_PATH = Path("database/content.db")
REPORT_PATH = Path("database/migration_report.json")


def value_or_unknown(value):
    return value if value not in (None, "") else "UNKNOWN"


def normalize_sql_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return None
    return value


def normalize_records(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        if isinstance(data.get("assets"), list):
            return data["assets"]

        if all(isinstance(v, dict) for v in data.values()):
            records = []
            for key, value in data.items():
                item = dict(value)
                item.setdefault("content_id", key)
                records.append(item)
            return records

    raise ValueError(f"Unsupported registry format: {type(data).__name__}")


def migrate():
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    records = normalize_records(raw)

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
    failed = []

    for item in records:
        content_id = "UNKNOWN"
        try:
            if not isinstance(item, dict):
                raise TypeError(f"record type {type(item).__name__} is not supported")

            content_id = value_or_unknown(item.get("content_id"))

            values = [
                item.get("content_id"),
                item.get("topic"),
                item.get("category"),
                item.get("script_source"),
                item.get("video_source"),
                item.get("generator"),
                item.get("video_file"),
                item.get("artifact_id"),
                item.get("production_status"),
                item.get("publish_status"),
                item.get("platforms", {}),
                item.get("postiz_id"),
                item.get("published_url"),
                item.get("analytics_status"),
            ]

            cur.execute("""
            INSERT OR REPLACE INTO videos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, tuple(
                normalize_sql_value(value_or_unknown(value))
                for value in values
            ))
            imported += 1
        except Exception as exc:
            failed.append({
                "content_id": content_id,
                "error": str(exc)
            })

    conn.commit()
    conn.close()

    REPORT_PATH.write_text(json.dumps({
        "imported_records": imported,
        "skipped_records": skipped,
        "failed_records": failed,
        "status": "completed" if not failed else "failed"
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    migrate()
