from data.database_path import database_path
import json
import os
import sqlite3
from datetime import datetime

DB_PATH = database_path()


def _connect():
    database_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT,
            video_id TEXT,
            platform TEXT,
            account_id INTEGER,
            status TEXT,
            scheduled_time TEXT,
            title TEXT,
            description TEXT,
            tags TEXT,
            privacy_status TEXT,
            platform_video_id TEXT,
            published_url TEXT,
            error_message TEXT,
            provider_operation_id TEXT,
            provider_operation_status TEXT,
            provider_operation_updated_at TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    columns = {row["name"] for row in cursor.execute("PRAGMA table_info(publish_tasks)").fetchall()}
    migrations = {
        "asset_id": "TEXT",
        "account_id": "INTEGER",
        "title": "TEXT",
        "description": "TEXT",
        "tags": "TEXT",
        "privacy_status": "TEXT",
        "platform_video_id": "TEXT",
        "published_url": "TEXT",
        "error_message": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
        "provider_operation_id": "TEXT",
        "provider_operation_status": "TEXT",
        "provider_operation_updated_at": "TEXT",
    }
    for name, field_type in migrations.items():
        if name not in columns:
            cursor.execute(f"ALTER TABLE publish_tasks ADD COLUMN {name} {field_type}")

    cursor.execute("UPDATE publish_tasks SET description='' WHERE description IS NULL")
    cursor.execute("UPDATE publish_tasks SET tags='[]' WHERE tags IS NULL OR tags=''")
    cursor.execute(
        "UPDATE publish_tasks SET privacy_status='private' "
        "WHERE privacy_status IS NULL OR privacy_status=''"
    )
    conn.commit()
    conn.close()


def _serialize(row):
    if not row:
        return None
    data = dict(row)
    raw_tags = data.get("tags")
    if isinstance(raw_tags, list):
        data["tags"] = raw_tags
    else:
        try:
            parsed = json.loads(raw_tags or "[]")
            data["tags"] = parsed if isinstance(parsed, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            data["tags"] = []
    data["description"] = data.get("description") or ""
    data["privacy_status"] = data.get("privacy_status") or "private"
    return data


def _task_value(task, name, default=None):
    if isinstance(task, dict):
        return task.get(name, default)
    return getattr(task, name, default)


def create_publish_task(task):
    _init_db()
    now = datetime.utcnow().isoformat()
    conn = _connect()
    cursor = conn.execute(
        """
        INSERT INTO publish_tasks
        (asset_id, video_id, platform, account_id, status, scheduled_time,
         title, description, tags, privacy_status, provider_operation_id,
         provider_operation_status, provider_operation_updated_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _task_value(task, "asset_id"),
            _task_value(task, "video_id"),
            _task_value(task, "platform"),
            _task_value(task, "account_id"),
            _task_value(task, "status", "pending"),
            _task_value(task, "scheduled_time"),
            _task_value(task, "title"),
            _task_value(task, "description", "") or "",
            json.dumps(_task_value(task, "tags", []) or [], ensure_ascii=False),
            _task_value(task, "privacy_status", "private") or "private",
            _task_value(task, "provider_operation_id"),
            _task_value(task, "provider_operation_status"),
            _task_value(task, "provider_operation_updated_at"),
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
    conn = _connect()
    rows = conn.execute("SELECT * FROM publish_tasks ORDER BY id").fetchall()
    conn.close()
    return [_serialize(row) for row in rows]


def get_publish_task(task_id):
    _init_db()
    conn = _connect()
    row = conn.execute("SELECT * FROM publish_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return _serialize(row)


def update_publish_status(
    task_id,
    status,
    platform_video_id=None,
    published_url=None,
    error_message=None,
    provider_operation_id=None,
    provider_operation_status=None,
):
    _init_db()
    conn = _connect()
    conn.execute(
        """
        UPDATE publish_tasks
        SET status=?, platform_video_id=COALESCE(?, platform_video_id),
            published_url=COALESCE(?, published_url), error_message=?,
            provider_operation_id=COALESCE(?, provider_operation_id),
            provider_operation_status=COALESCE(?, provider_operation_status),
            provider_operation_updated_at=?, updated_at=?
        WHERE id=?
        """,
        (
            status,
            platform_video_id,
            published_url,
            error_message,
            provider_operation_id, provider_operation_status,
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat(),
            task_id,
        ),
    )
    conn.commit()
    conn.close()
    return get_publish_task(task_id)


def claim_publish_task(task_id):
    _init_db()
    conn = _connect()
    cursor = conn.execute(
        "UPDATE publish_tasks SET status='publishing', updated_at=? "
        "WHERE id=? AND status IN ('pending','failed')",
        (datetime.utcnow().isoformat(), task_id),
    )
    conn.commit(); conn.close()
    return cursor.rowcount == 1
