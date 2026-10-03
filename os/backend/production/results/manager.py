from data.database_path import database_path
import json
import sqlite3
from datetime import datetime

from assets.binding import create_asset_from_result

DB_PATH = database_path()


def _connect():
    conn = sqlite3.connect(database_path())
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
        "promotion_state": "TEXT",
        "promotion_metadata": "TEXT",
    }
    for name, field_type in migrations.items():
        if name not in columns:
            cursor.execute(f"ALTER TABLE production_results ADD COLUMN {name} {field_type}")
    duplicates = cursor.execute("SELECT runtime_job_id FROM production_results WHERE runtime_job_id IS NOT NULL GROUP BY runtime_job_id HAVING COUNT(*) > 1").fetchall()
    if not duplicates:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_production_results_runtime_job ON production_results(runtime_job_id) WHERE runtime_job_id IS NOT NULL")
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
    asset_status = binding.get("asset_status") or ("ready" if asset_id else "failed")

    conn = _connect()
    conn.execute(
        "UPDATE production_results SET asset_id=?, asset_status=?, updated_at=? WHERE id=?",
        (asset_id, asset_status, datetime.utcnow().isoformat(), result["id"]),
    )
    conn.commit()
    conn.close()
    return binding


def _fail_asset_binding(result_id, binding):
    conn = _connect()
    conn.execute(
        "UPDATE production_results SET status='failed', asset_status='failed', error=?, updated_at=? WHERE id=?",
        (
            binding.get("error") or "Video Asset binding failed",
            datetime.utcnow().isoformat(),
            result_id,
        ),
    )
    conn.commit()
    conn.close()


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
    existing = conn.execute("SELECT * FROM production_results WHERE runtime_job_id=?", (data["runtime_job_id"],)).fetchone()
    if existing:
        if existing["provider"] != data["provider"]:
            conn.close()
            raise ValueError("ProductionResult provider binding mismatch")
        conn.close()
        return _serialize(existing)
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
    if result and result.get("status") == "completed" and not any((result.get("output") or {}).get(k) for k in ('defer_asset_binding', 'g4b_no_asset_binding')):
        binding = _bind_asset(result)
        if not binding.get("asset_id"):
            _fail_asset_binding(result_id, binding)
        result = get_result(result_id)
    if result and result.get("status") in {"completed", "failed"}:
        _sync_terminal_status(result, result["status"])
    return get_result(result_id)


def create_or_get_result_for_job(data):
    """Race-safe canonical result creation for one RuntimeJob."""
    init_results_table()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        duplicate_count = conn.execute("SELECT COUNT(*) FROM production_results WHERE runtime_job_id=?", (data["runtime_job_id"],)).fetchone()[0]
        if duplicate_count > 1:
            raise ValueError("multiple ProductionResults for RuntimeJob")
        row = conn.execute("SELECT * FROM production_results WHERE runtime_job_id=?", (data["runtime_job_id"],)).fetchone()
        if row:
            if row["provider"] != data["provider"]:
                raise ValueError("ProductionResult provider binding mismatch")
            conn.commit()
            return _serialize(row)
        now = datetime.utcnow().isoformat()
        output = data.get("output") or {}
        video_id = data.get("video_id") or (output.get("video_id") or output.get("content_id") if isinstance(output, dict) else None)
        cur = conn.execute("INSERT INTO production_results (runtime_job_id,video_id,provider,asset_id,asset_status,status,output,error,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (data["runtime_job_id"], video_id, data["provider"], data.get("asset_id"), data.get("asset_status"), data.get("status", "created"), json.dumps(output, ensure_ascii=False), data.get("error"), now, now))
        row = conn.execute("SELECT * FROM production_results WHERE id=?", (cur.lastrowid,)).fetchone()
        conn.commit()
        return _serialize(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_results():
    init_results_table()
    conn = _connect()
    rows = conn.execute("SELECT * FROM production_results ORDER BY id").fetchall()
    conn.close()
    return [_serialize(row) for row in rows]


def persist_deferred_ai_response(runtime_job_id, response, *, recovery=False):
    """Atomically seal existing AI result/job/task; no asset creation or network.

    The initial row is created by create_or_get_result_for_job. Poll races are
    serialized here so a late active response cannot overwrite terminal output.
    """
    status = response.get('status')
    if status not in {'submitted', 'running', 'completed', 'failed'}:
        raise ValueError('invalid AI response status')
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        rows = conn.execute('SELECT * FROM production_results WHERE runtime_job_id=?', (runtime_job_id,)).fetchall()
        job = conn.execute('SELECT * FROM runtime_jobs WHERE id=?', (runtime_job_id,)).fetchone()
        if len(rows) != 1 or not job or rows[0]['provider'] != 'ai_gateway' or job['provider'] != 'ai_gateway':
            raise ValueError('AI result linkage invalid')
        row = rows[0]
        task = conn.execute('SELECT * FROM production_tasks WHERE id=?', (job['task_id'],)).fetchone()
        if not task or task['provider'] != 'ai_gateway':
            raise ValueError('AI task linkage invalid')
        params = json.loads(task['parameters'] or '{}')
        if row['video_id'] != params.get('content_id'):
            raise ValueError('AI result identity or asset boundary invalid')
        if row['asset_id']:
            # A later G4-D PASS is a valid terminal replay, not an execution
            # side-effect. Validate the existing quality binding without I/O.
            from assets.quality import _binding, _quality_row
            if row['status'] != 'completed':
                raise ValueError('AI result asset boundary invalid')
            _binding(conn, row, _quality_row(conn, row['id']))
        current_output = json.loads(row['output'] or '{}')
        if row['status'] in {'completed', 'failed'} or (recovery and current_output.get('content_id')):
            expected_status = row['status'] if row['status'] in {'completed', 'failed'} else 'running'
            if task['status'] != expected_status or job['status'] != expected_status:
                raise ValueError('AI result/job/task state mismatch')
            conn.commit()
            return _serialize(row)
        if task['status'] not in {'scheduled', 'running'} or job['status'] not in {'created', 'running'}:
            raise ValueError('AI lifecycle state mismatch')
        output = {**(response.get('output') or {}), 'defer_asset_binding': True}
        # Preserve terminal correlation and reject a remote identity switch.
        for key in ('remote_job_id', 'job_id', 'status_url'):
            if current_output.get(key) and output.get(key) and current_output[key] != output[key]:
                raise ValueError('AI remote correlation changed')
        now = datetime.utcnow().isoformat()
        encoded = json.dumps(output, ensure_ascii=False)
        runtime_status = status if status in {'completed', 'failed'} else 'running'
        conn.execute('UPDATE production_results SET status=?,output=?,error=?,updated_at=? WHERE id=?',
                     (status, encoded, response.get('error'), now, row['id']))
        conn.execute('UPDATE runtime_jobs SET status=?,output=?,error=?,updated_at=? WHERE id=?',
                     (runtime_status, encoded, response.get('error'), now, runtime_job_id))
        conn.execute('UPDATE production_tasks SET status=?,updated_at=? WHERE id=?',
                     (runtime_status, now, task['id']))
        result = conn.execute('SELECT * FROM production_results WHERE id=?', (row['id'],)).fetchone()
        conn.commit()
        return _serialize(result)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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


def claim_result_for_completion(result_id):
    """Atomically claim a submitted result for its single completion owner."""
    init_results_table()
    conn = _connect()
    cursor = conn.execute(
        "UPDATE production_results SET status='running', updated_at=? WHERE id=? AND status='submitted'",
        (datetime.utcnow().isoformat(), result_id),
    )
    conn.commit()
    conn.close()
    return cursor.rowcount == 1

def claim_promotion_execution(result_id, intent):
    """Atomically claim the promotion side effect before any external POST."""
    init_results_table()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "UPDATE production_results SET status='running', promotion_state='intent', promotion_metadata=?, updated_at=? "
            "WHERE id=? AND promotion_state IS NULL AND status IN ('submitted','running') AND provider='github'",
            (json.dumps(intent or {}, ensure_ascii=False), datetime.utcnow().isoformat(), result_id),
        )
        conn.commit()
        return cur.rowcount == 1
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def claim_human_promotion_resume(result_id, *, expected_intent):
    """Durably consume the single human-authorized POST opportunity.

    A missing run ID is not enough to permit another POST after a crash.  The
    claim marker is committed before network I/O and can never be cleared.
    """
    init_results_table()
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute(
            "SELECT status,provider,promotion_state,promotion_metadata FROM production_results WHERE id=?",
            (result_id,),
        ).fetchone()
        if not row or row['status'] != 'running' or row['provider'] != 'github' or row['promotion_state'] != 'intent':
            conn.commit()
            return False
        intent = json.loads(row['promotion_metadata'] or '{}')
        if any(intent.get(key) != value for key, value in expected_intent.items()):
            raise ValueError('Human promotion intent linkage changed')
        if intent.get('promotion_run_id') or intent.get('recovery_required') or intent.get('human_resume_post_claimed_at'):
            conn.commit()
            return False
        intent['human_resume_post_claimed_at'] = datetime.utcnow().isoformat()
        conn.execute(
            'UPDATE production_results SET promotion_metadata=?,updated_at=? WHERE id=?',
            (json.dumps(intent, ensure_ascii=False), datetime.utcnow().isoformat(), result_id),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def update_promotion_state(result_id, state, metadata=None):
    init_results_table()
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT promotion_state,promotion_metadata FROM production_results WHERE id=?', (result_id,)).fetchone()
        allowed = {'intent': {'intent','submitted','running','completed','failed'}, 'submitted': {'submitted','running','completed','failed'}, 'running': {'running','completed','failed'}, 'completed': {'completed'}, 'failed': {'failed'}}
        if not row or state not in allowed.get(row['promotion_state'], set()):
            raise ValueError('Invalid promotion state transition')
        current = json.loads(row['promotion_metadata'] or '{}')
        for key, value in (metadata or {}).items():
            if key in current and key not in {'promotion_run_status','promotion_run_conclusion','promotion_run_url','recovery_required'} and current[key] != value:
                raise ValueError('Promotion correlation metadata is immutable')
        if row['promotion_state'] not in {'completed','failed'}:
            current.update(metadata or {})
            conn.execute('UPDATE production_results SET promotion_state=?,promotion_metadata=?,updated_at=? WHERE id=? AND promotion_state=?', (state,json.dumps(current),datetime.utcnow().isoformat(),result_id,row['promotion_state']))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return get_result(result_id)

def claim_failed_result_for_recovery(result_id):
    init_results_table(); conn=_connect(); cur=conn.execute("UPDATE production_results SET status='running', updated_at=? WHERE id=? AND status='failed'",(datetime.utcnow().isoformat(),result_id)); conn.commit(); conn.close(); return cur.rowcount==1


def update_result(result_id, *, status=None, output=None, error=None, bind_asset=True):
    init_results_table()
    current = get_result(result_id)
    if not current:
        return None

    next_status = status if status is not None else current.get("status")
    current_status = current.get("status")
    allowed = {
        "submitted": {"submitted", "running", "completed", "failed"},
        "running": {"running", "completed", "failed"},
        "completed": {"completed"},
        "failed": {"failed"},
    }
    if current_status in allowed and next_status not in allowed[current_status]:
        raise ValueError(f"Invalid ProductionResult status transition: {current_status} -> {next_status}")
    next_output = output if output is not None else current.get("output") or {}
    if (current.get("output") or {}).get("defer_asset_binding"):
        next_output = {**next_output, "defer_asset_binding": True}
    if (current.get("output") or {}).get("g4b_no_asset_binding"):
        next_output = {**next_output, "g4b_no_asset_binding": True}
    next_error = error if error is not None else current.get("error")

    conn = _connect()
    cursor = conn.execute(
        """
        UPDATE production_results
        SET status=?, output=?, error=?, updated_at=?
        WHERE id=? AND status=?
        """,
        (
            next_status,
            json.dumps(next_output, ensure_ascii=False),
            next_error,
            datetime.utcnow().isoformat(),
            result_id,
            current_status,
        ),
    )
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return get_result(result_id)

    result = get_result(result_id)
    if result and next_status == "completed" and bind_asset and not any(next_output.get(k) for k in ('defer_asset_binding', 'g4b_no_asset_binding')) and not result.get("asset_id"):
        binding = _bind_asset(result)
        if not binding.get("asset_id"):
            _fail_asset_binding(result_id, binding)
        result = get_result(result_id)

    if result and result.get("status") in {"completed", "failed"}:
        _sync_terminal_status(result, result["status"])
    return get_result(result_id)


def update_result_status(result_id, status):
    return update_result(result_id, status=status)


def complete_recovered_result(result_id, *, output):
    """Finalize a verified external recovery without weakening normal transitions."""
    init_results_table()
    current = get_result(result_id)
    if not current:
        raise ValueError("ProductionResult not found")
    if current.get("status") == "completed":
        from production.runtime.manager import get_job
        from production.tasks.manager import get_task
        job = get_job(current.get("runtime_job_id"))
        task = get_task(job.get("task_id")) if job else None
        if not job or not task or str(job.get("task_id")) != str(task.id):
            raise ValueError("Completed recovery lifecycle is inconsistent")
        if job.get("status") != "completed" or task.status != "completed":
            raise ValueError("Completed recovery lifecycle is inconsistent")
        if not current.get("asset_id") or current.get("asset_status") != "ready":
            raise ValueError("Completed recovery result has invalid asset state")
        return current
    if current.get("status") != "running":
        raise ValueError("Recovery result must be running")
    video_id = current.get("video_id")
    runtime_job_id = current.get("runtime_job_id")
    if not video_id or runtime_job_id is None:
        raise ValueError("Recovery result linkage is incomplete")
    from production.runtime.manager import get_job
    from production.tasks.manager import get_task
    job = get_job(runtime_job_id)
    task = get_task(job.get("task_id")) if job else None
    if not job or not task or str(job.get("task_id")) != str(task.id):
        raise ValueError("Recovery result linkage is inconsistent")
    if job.get("status") != "failed" or task.status != "failed":
        raise ValueError("Recovery lifecycle state is not recoverable")
    url = (output or {}).get("asset_url") or (output or {}).get("url")
    if (output or {}).get("storage_type") != "github_pages" or not (isinstance(url, str) and url.startswith("https://")):
        raise ValueError("Verified recovery output is missing a secure promoted asset")
    asset = None
    if current.get("asset_id"):
        from assets.manager import get_asset_by_asset_id
        asset = get_asset_by_asset_id(current["asset_id"])
    if not asset:
        binding = _bind_asset(dict(current, output=output))
        if not binding.get("asset_id") or binding.get("asset_status") != "ready":
            raise ValueError("Recovered asset binding is not ready")
        current = get_result(result_id)
        asset = {"asset_id": current.get("asset_id"), "status": current.get("asset_status")}
    if asset.get("status") != "ready":
        raise ValueError("Recovered asset is not ready")
    now = datetime.utcnow().isoformat()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT status FROM production_results WHERE id=?", (result_id,)).fetchone()
        if not row or row["status"] != "running":
            raise ValueError("Recovery result was concurrently finalized")
        conn.execute("UPDATE production_results SET status='completed', output=?, error='', asset_status='ready', updated_at=? WHERE id=?", (json.dumps(output or {}, ensure_ascii=False), now, result_id))
        conn.execute("UPDATE runtime_jobs SET status='completed', updated_at=? WHERE id=?", (now, runtime_job_id))
        conn.execute("UPDATE production_tasks SET status='completed', updated_at=? WHERE id=?", (now, job["task_id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return get_result(result_id)
