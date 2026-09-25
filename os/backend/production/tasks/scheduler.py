import json

import sqlite3
from datetime import datetime
from data.database_path import database_path
from production.runtime.manager import init_runtime_table, get_jobs_for_task
from production.runtime.state import JOB_CREATED
from .execution import require_execution_ready
from .manager import update_task_status, get_task


VALID_TRANSITIONS = {
    "created": {"queued", "failed"},
    "queued": {"scheduled", "failed"},
    "scheduled": {"running", "failed"},
    "running": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


def transition_task(task, target_status):
    current = getattr(task, "status", "created")
    if target_status == current:
        return task

    if target_status not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(
            f"Invalid ProductionTask status transition: {current} -> {target_status}"
        )

    if getattr(task, "id", None) is None:
        raise ValueError("ProductionTask must be persisted before status transition")

    return update_task_status(task.id, target_status, expected_status=current)


def claim_runtime_job(task, failure_hook=None):
    """Atomically claim one durable RuntimeJob for a ProductionTask."""
    if getattr(task, "id", None) is None:
        raise ValueError("ProductionTask must have a stable id before scheduling")
    require_execution_ready(task)
    job_type = "github_runtime" if task.provider == "github" else "ai_runtime"
    payload = {
        "objective": task.objective,
        "template": task.template,
        "parameters": task.parameters,
        "resources": task.resources,
        "task_type": task.task_type,
        "workflow": task.workflow,
        "branch": task.branch,
    }
    input_value = json.dumps(payload, ensure_ascii=False)
    now = datetime.utcnow().isoformat()
    init_runtime_table()
    with sqlite3.connect(database_path(), timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM production_tasks WHERE id=?", (task.id,)).fetchone()
        if not row:
            raise ValueError("ProductionTask not found")
        current_status = row["status"] or "created"
        jobs = conn.execute("SELECT * FROM runtime_jobs WHERE task_id=? ORDER BY id", (task.id,)).fetchall()
        if len(jobs) > 1:
            raise ValueError("multiple RuntimeJobs for ProductionTask")
        if jobs:
            job = jobs[0]
            if job["provider"] != row["provider"] or job["job_type"] != job_type:
                raise ValueError("RuntimeJob provider binding mismatch")
            if current_status not in {"scheduled", "running"}:
                raise ValueError("RuntimeJob and ProductionTask state mismatch")
            return dict(job)
        if current_status != "created":
            raise ValueError("ProductionTask has no recoverable RuntimeJob")
        cur = conn.execute("UPDATE production_tasks SET status='scheduled', updated_at=? WHERE id=? AND status='created'", (now, task.id))
        if cur.rowcount != 1:
            raise ValueError("ProductionTask claim compare-and-swap conflict")
        if failure_hook:
            failure_hook()
        cur = conn.execute("INSERT INTO runtime_jobs(task_id,job_type,provider,status,input,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (task.id, job_type, row["provider"], JOB_CREATED, input_value, now, now))
        job = conn.execute("SELECT * FROM runtime_jobs WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(job)


def schedule_task(task):
    """Validate execution, persist scheduling state, and create a Runtime Job."""
    if getattr(task, "id", None) is None:
        raise ValueError("ProductionTask must have a stable id before scheduling")

    return claim_runtime_job(task)
