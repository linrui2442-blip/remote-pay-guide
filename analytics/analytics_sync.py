import json
from pathlib import Path

OUTPUT = Path("analytics/analytics_report.json")

SYNC_MODE = "read_only"
REGISTRY_WRITE = False
DATABASE_WRITE = False


def normalize(value):
    if value in (None, ""):
        return "UNKNOWN"
    return value


def generate_report():
    report = {
        "sync_mode": SYNC_MODE,
        "source": "analytics-source",
        "registry_write": REGISTRY_WRITE,
        "database_write": DATABASE_WRITE,
        "records_processed": 0,
        "records_failed": 0,
        "records": []
    }

    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    generate_report()
