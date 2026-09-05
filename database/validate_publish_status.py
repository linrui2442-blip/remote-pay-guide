import sqlite3
from pathlib import Path

DB_PATH = Path("database/content.db")


def validate():
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='publish_status'"
        ).fetchone()
        return row is not None


if __name__ == "__main__":
    if not validate():
        raise SystemExit("publish_status table missing")
    print("publish_status table exists")
