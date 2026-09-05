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
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    columns = [row[1] for row in cursor.execute("PRAGMA table_info(publish_tasks)").fetchall()]
    if "account_id" not in columns:
        cursor.execute("ALTER TABLE publish_tasks ADD COLUMN account_id INTEGER")

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
    rows = conn.execute(
        "SELECT id, video_id, platform, account_id, status, scheduled_time FROM publish_tasks"
    ).fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "video_id": row[1],
            "platform": row[2],
            "account_id": row[3],
            "status": row[4],
            "scheduled_time": row[5],
        }
        for row in rows
    ]


def get_publish_task(task_id):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, video_id, platform, account_id, status, scheduled_time FROM publish_tasks WHERE id=?",
        (task_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "video_id": row[1],
        "platform": row[2],
        "account_id": row[3],
        "status": row[4],
        "scheduled_time": row[5],
    }


def update_publish_status(task_id, status):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE publish_tasks SET status=?, updated_at=? WHERE id=?",
        (status, datetime.utcnow().isoformat(), task_id),
    )
    conn.commit()
    conn.close()
