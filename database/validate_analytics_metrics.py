import sqlite3
from pathlib import Path

DB_PATH = Path("database/content.db")


def validate():
    conn = sqlite3.connect(DB_PATH)
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_metrics'"
    ).fetchone()
    conn.close()
    return result is not None


if __name__ == "__main__":
    if not validate():
        raise SystemExit("analytics_metrics table missing")
    print("analytics_metrics table exists")
