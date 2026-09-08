from data.database_path import database_path
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict

from .models import ProductionTask

DB_PATH = database_path()


def _connect():
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_tasks_table():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS production_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            objective TEXT,
            provider TEXT,
            template TEXT,
            parameters TEXT,
            resources TEXT,
            priority INTEGER,
            status TEXT,
            task_type TEXT,
            workflow TEXT,
            branch TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    columns = {row["name"] for row in cursor.execute("PRAGMA table_info(production_tasks)").fetchall()}
    migrations = {
        "source": "TEXT",
        "objective": "TEXT",
        "provider": "TEXT",
        "template": "TEXT",
        "parameters": "TEXT",
        "resources": "TEXT",
        "priority": "INTEGER",
        "status": "TEXT",
        "task_type": "TEXT",
        "workflow": "TEXT",
        "branch": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }
    for name, field_type in migrations.items():
        if name not in columns:
            cursor.execute(f"ALTER TABLE production_tasks ADD COLUMN {name} {field_type}")

    now = datetime.utcnow().isoformat()
    cursor.execute("UPDATE production_tasks SET source='legacy' WHERE source IS NULL OR source=''")
    cursor.execute("UPDATE production_tasks SET objective='' WHERE objective IS NULL")
    cursor.execute("UPDATE production_tasks SET template='' WHERE template IS NULL")
    cursor.execute("UPDATE production_tasks SET parameters='{}' WHERE parameters IS NULL OR parameters=''")
    cursor.execute("UPDATE production_tasks SET resources='[]' WHERE resources IS NULL OR resources=''")
    cursor.execute("UPDATE production_tasks SET priority=0 WHERE priority IS NULL")
    cursor.execute("UPDATE production_tasks SET status='created' WHERE status IS NULL OR status='' OR status='pending'")
    cursor.execute("UPDATE production_tasks SET task_type='' WHERE task_type IS NULL")
    cursor.execute("UPDATE production_tasks SET workflow='' WHERE workflow IS NULL")
    cursor.execute("UPDATE production_tasks SET branch='main' WHERE branch IS NULL OR branch=''")
    cursor.execute("UPDATE production_tasks SET created_at=? WHERE created_at IS NULL OR created_at=''", (now,))
    cursor.execute("UPDATE production_tasks SET updated_at=? WHERE updated_at IS NULL OR updated_at=''", (now,))
    conn.commit()
    conn.close()


def _json_load(value: Any, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _row_to_task(row) -> ProductionTask:
    return ProductionTask(
        id=row["id"],
        source=row["source"] or "legacy",
        objective=row["objective"] or "",
        provider=row["provider"] or "github",
        template=row["template"] or "",
        parameters=_json_load(row["parameters"], {}),
        resources=_json_load(row["resources"], []),
        priority=int(row["priority"] or 0),
        status=row["status"] or "created",
        task_type=row["task_type"] or "",
        workflow=row["workflow"] or "",
        branch=row["branch"] or "main",
        created_at=row["created_at"] or datetime.utcnow().isoformat(),
        updated_at=row["updated_at"] or datetime.utcnow().isoformat(),
    )


def create_task(task: ProductionTask | Dict[str, Any]) -> ProductionTask:
    init_tasks_table()
    if isinstance(task, dict):
        task = ProductionTask(**task)

    # Preserve the old Production Center API contract while normalizing into
    # the canonical lifecycle before validation/persistence.
    if task.status == "pending":
        task.status = "created"

    task.validate()
    now = datetime.utcnow().isoformat()
    conn = _connect()
    cursor = conn.execute(
        """
        INSERT INTO production_tasks
        (source, objective, provider, template, parameters, resources, priority,
         status, task_type, workflow, branch, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task.source,
            task.objective,
            task.provider,
            task.template,
            json.dumps(task.parameters or {}, ensure_ascii=False),
            json.dumps(task.resources or [], ensure_ascii=False),
            task.priority,
            task.status,
            task.task_type,
            task.workflow,
            task.branch,
            now,
            now,
        ),
    )
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return get_task(task_id)


def get_tasks():
    init_tasks_table()
    conn = _connect()
    rows = conn.execute("SELECT * FROM production_tasks ORDER BY id").fetchall()
    conn.close()
    return [_row_to_task(row) for row in rows]


def get_task(task_id):
    init_tasks_table()
    conn = _connect()
    row = conn.execute("SELECT * FROM production_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return _row_to_task(row) if row else None


def update_task_status(task_id: int, status: str):
    init_tasks_table()
    conn = _connect()
    conn.execute(
        "UPDATE production_tasks SET status=?, updated_at=? WHERE id=?",
        (status, datetime.utcnow().isoformat(), task_id),
    )
    conn.commit()
    conn.close()
    return get_task(task_id)
