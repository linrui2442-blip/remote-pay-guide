import json
import sqlite3
from datetime import datetime
from .state import JOB_CREATED

DB_PATH = "os/database/os.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _decode_json(value):
    if value in (None, ""):
        return value
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return value


def _serialize(row):
    if not row:
        return None
    data = dict(row)
    data["output"] = _decode_json(data.get("output"))
    return data


def init_runtime_table():
    conn = _connect()
    conn.execute("""CREATE TABLE IF NOT EXISTS runtime_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        job_type TEXT,
        provider TEXT,
        status TEXT,
        input TEXT,
        output TEXT,
        error TEXT,
        created_at TEXT,
        updated_at TEXT
    )""")
    conn.commit()
    conn.close()


def create_job(data):
    init_runtime_table()
    now = datetime.utcnow().isoformat()
    input_value = data.get("input", "{}")
    if isinstance(input_value, (dict, list)):
        input_value = json.dumps(input_value, ensure_ascii=False)
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO runtime_jobs(task_id,job_type,provider,status,input,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (
            data["task_id"],
            data["job_type"],
            data["provider"],
            JOB_CREATED,
            input_value,
            now,
            now,
        ),
    )
    conn.commit()
    job = get_job(cur.lastrowid)
    conn.close()
    return job


def get_jobs():
    init_runtime_table()
    conn = _connect()
    rows = conn.execute("SELECT * FROM runtime_jobs ORDER BY id").fetchall()
    conn.close()
    return [_serialize(row) for row in rows]


def get_job(job_id):
    init_runtime_table()
    conn = _connect()
    row = conn.execute("SELECT * FROM runtime_jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    return _serialize(row)


def get_latest_job_for_task(task_id):
    init_runtime_table()
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM runtime_jobs WHERE task_id=? ORDER BY id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    conn.close()
    return _serialize(row)


def update_job_status(job_id, status):
    init_runtime_table()
    conn = _connect()
    conn.execute(
        "UPDATE runtime_jobs SET status=?,updated_at=? WHERE id=?",
        (status, datetime.utcnow().isoformat(), job_id),
    )
    conn.commit()
    conn.close()


def update_job_result(job_id, output=None, error=None):
    init_runtime_table()
    output_value = output
    if isinstance(output, (dict, list)):
        output_value = json.dumps(output, ensure_ascii=False)
    conn = _connect()
    conn.execute(
        "UPDATE runtime_jobs SET output=?,error=?,updated_at=? WHERE id=?",
        (output_value, error, datetime.utcnow().isoformat(), job_id),
    )
    conn.commit()
    conn.close()
    return get_job(job_id)
