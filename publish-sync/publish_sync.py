"""
Read-only Publish Sync Layer foundation.

Source:
    publish-state

Output:
    sync_report.json

This module does not:
- publish content
- call external APIs
- update registry
- write database
"""

import json
from pathlib import Path

SYNC_MODE = "read_only"
REGISTRY_WRITE = False

SOURCE_DIR = Path("publish-state")
OUTPUT_FILE = Path("publish-sync/sync_report.json")


def normalize_value(value):
    """Convert missing values without modifying source data."""
    if value is None or value == "":
        return "UNKNOWN"
    return value


def build_report():
    records = []
    failed = 0

    if SOURCE_DIR.exists():
        for item in SOURCE_DIR.glob("*.json"):
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
                records.append(
                    {
                        "content_id": normalize_value(data.get("content_id")),
                        "postiz_id": normalize_value(data.get("postiz_id")),
                        "platforms": data.get("platforms", "UNKNOWN"),
                    }
                )
            except Exception:
                failed += 1

    return {
        "sync_mode": SYNC_MODE,
        "source": "publish-state",
        "registry_write": REGISTRY_WRITE,
        "records_processed": len(records),
        "records_failed": failed,
        "records": records,
    }


if __name__ == "__main__":
    OUTPUT_FILE.write_text(
        json.dumps(build_report(), indent=2),
        encoding="utf-8",
    )
