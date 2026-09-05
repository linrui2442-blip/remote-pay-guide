import sqlite3
from datetime import datetime

DB_PATH = "os/database/os.db"


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            platform TEXT,
            account_id INTEGER,
            status TEXT,
            scheduled_time TEXT,
            platform_video_id TEXT,
            published_url TEXT,
            error_message TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    columns = [row[1] for row in cursor.execute("PRAGMA table_info(publish_tasks)").fetchall()]
    migrations = {
        "account_id": "INTEGER",
        "platform_video_id": "TEXT",
        "published_url": "TEXT",
        "error_message": "TEXT",
    }

    for name, field_type in migrations.items():
        if name not in columns:
            cursor.execute(f"ALTER TABLE publish_tasks ADD COLUMN {name} {field_type}")

    conn.commit()
    conn.close()


def create_publish_task(task):
    _init_db()
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        INSERT INTO publish_tasks
        (video_id, platform, account_id, status, scheduled_time, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task.video_id,
            task.platform,
            getattr(task, "account_id", None),
            task.status,
            task.scheduled_time,
            now,
            now,
        ),
    )
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return get_publish_task(task_id)


def get_publish_tasks():
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM publish_tasks").fetchall()
    conn.close()
    return rows


def get_publish_task(task_id):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT * FROM publish_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return row


def update_publish_status(task_id, status, platform_video_id=None, published_url=None, error_message=None):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        UPDATE publish_tasks
        SET status=?, platform_video_id=?, published_url=?, error_message=?, updated_at=?
        WHERE id=?
        """,
        (
            status,
            platform_video_id,
            published_url,
            error_message,
            datetime.utcnow().isoformat(),
            task_id,
        ),
    )
    conn.commit()
    conn.close()
