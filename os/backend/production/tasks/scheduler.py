import json

from production.runtime.manager import create_job
from .manager import update_task_status


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

    return update_task_status(task.id, target_status)


def schedule_task(task):
    """Persist scheduling state and create a Runtime Job for a canonical task."""
    if getattr(task, "id", None) is None:
        raise ValueError("ProductionTask must have a stable id before scheduling")

    task = transition_task(task, "queued")
    task = transition_task(task, "scheduled")

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

    return create_job(
        {
            "task_id": task.id,
            "job_type": job_type,
            "provider": task.provider,
            "input": json.dumps(payload, ensure_ascii=False),
        }
    )
