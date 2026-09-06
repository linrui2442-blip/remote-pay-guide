import json
import sqlite3
from datetime import datetime

from assets.binding import create_asset_from_result

DB_PATH = "os/database/os.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_results_table():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS production_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            runtime_job_id INTEGER,
            video_id TEXT,
            provider TEXT,
            asset_id TEXT,
            asset_status TEXT,
            status TEXT,
            output TEXT,
            error TEXT,
            created_at TEXT,
            updated_at TEXT
        )"""
    )
    columns = {row["name"] for row in cursor.execute("PRAGMA table_info(production_results)").fetchall()}
    migrations = {
        "video_id": "TEXT",
        "asset_status": "TEXT",
    }
    for name, field_type in migrations.items():
        if name not in columns:
            cursor.execute(f"ALTER TABLE production_results ADD COLUMN {name} {field_type}")
    conn.commit()
    conn.close()


def _decode_output(value):
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"raw": value}


def _serialize(row):
    if not row:
        return None
    data = dict(row)
    data["output"] = _decode_output(data.get("output"))
    return data


def _bind_asset(result):
    binding = create_asset_from_result(result)
    asset_id = binding.get("asset_id")
    asset_status = "ready" if asset_id else "failed"

    conn = _connect()
    conn.execute(
        "UPDATE production_results SET asset_id=?, asset_status=?, updated_at=? WHERE id=?",
        (asset_id, asset_status, datetime.utcnow().isoformat(), result["id"]),
    )
    conn.commit()
    conn.close()
    return binding


def _sync_terminal_status(result, status):
    if status not in {"completed", "failed"}:
        return

    from production.runtime.manager import get_job, update_job_status
    from production.runtime.state import JOB_COMPLETED, JOB_FAILED
    from production.tasks.manager import get_task
    from production.tasks.scheduler import transition_task

    job = get_job(result.get("runtime_job_id"))
    if not job:
        return

    update_job_status(
        job["id"],
        JOB_COMPLETED if status == "completed" else JOB_FAILED,
    )

    task = get_task(job.get("task_id"))
    if task and task.status != status:
        transition_task(task, status)


def create_result(data):
    init_results_table()
    now = datetime.utcnow().isoformat()
    output = data.get("output") or {}
    video_id = data.get("video_id")
    if not video_id and isinstance(output, dict):
        video_id = output.get("video_id") or output.get("content_id")
    if not video_id and data.get("runtime_job_id") is not None:
        video_id = str(data.get("runtime_job_id"))

    conn = _connect()
    cursor = conn.execute(
        """
        INSERT INTO production_results
        (runtime_job_id, video_id, provider, asset_id, asset_status, status,
         output, error, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["runtime_job_id"],
            video_id,
            data["provider"],
            data.get("asset_id"),
            data.get("asset_status"),
            data.get("status", "created"),
            json.dumps(output, ensure_ascii=False),
            data.get("error"),
            now,
            now,
        ),
    )
    conn.commit()
    result_id = cursor.lastrowid
    conn.close()

    result = get_result(result_id)
    if result and result.get("status") == "completed":
        _bind_asset(result)
    return get_result(result_id)


def get_results():
    init_results_table()
    conn = _connect()
    rows = conn.execute("SELECT * FROM production_results ORDER BY id").fetchall()
    conn.close()
    return [_serialize(row) for row in rows]


def get_result(result_id):
    init_results_table()
    conn = _connect()
    row = conn.execute("SELECT * FROM production_results WHERE id=?", (result_id,)).fetchone()
    conn.close()
    return _serialize(row)


def get_result_by_job(runtime_job_id):
    init_results_table()
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM production_results WHERE runtime_job_id=? ORDER BY id DESC LIMIT 1",
        (runtime_job_id,),
    ).fetchone()
    conn.close()
    return _serialize(row)


def update_result_status(result_id, status):
    init_results_table()
    conn = _connect()
    conn.execute(
        "UPDATE production_results SET status=?, updated_at=? WHERE id=?",
        (status, datetime.utcnow().isoformat(), result_id),
    )
    conn.commit()
    conn.close()

    result = get_result(result_id)
    if result and status == "completed" and not result.get("asset_id"):
        _bind_asset(result)
        result = get_result(result_id)

    if result:
        _sync_terminal_status(result, status)
    return get_result(result_id)
