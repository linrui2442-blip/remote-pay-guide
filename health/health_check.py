import json
import os
import sqlite3


REPORT_PATH = "health/health_report.json"


def check_file(path):
    return os.path.exists(path)


def check_database():
    result = {
        "component": "database",
        "status": "failed"
    }

    db = "database/content.db"
    if not os.path.exists(db):
        return result

    required = {
        "videos",
        "publish_status",
        "analytics_metrics"
    }

    conn = None
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        tables = {
            row[0]
            for row in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

        if required.issubset(tables):
            result["status"] = "ok"
    except sqlite3.Error:
        result["status"] = "failed"
    finally:
        if conn:
            conn.close()

    return result


def run_health_check():
    checks = []

    checks.append({
        "component": "registry",
        "status": "ok" if check_file("content-registry/registry.json") else "failed"
    })

    checks.append(check_database())

    checks.append({
        "component": "dashboard",
        "status": "ok" if check_file("dashboard/data/dashboard_data.json") else "failed"
    })

    checks.append({
        "component": "lifecycle",
        "status": "ok" if check_file("lifecycle/lifecycle_report.json") else "failed"
    })

    checks.append({
        "component": "workflow",
        "status": "ok" if check_file(".github/workflows") else "failed"
    })

    report = {
        "system_status": "healthy" if all(c["status"] == "ok" for c in checks) else "degraded",
        "checks": checks
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    run_health_check()
