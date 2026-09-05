from production.runtime.manager import create_job


VALID_TRANSITIONS = {
    "created": "queued",
    "queued": "scheduled",
    "scheduled": "running",
    "running": "completed",
}


def transition_task(task, target_status):
    current = getattr(task, "status", "created")

    if target_status == current:
        return task

    if VALID_TRANSITIONS.get(current) != target_status:
        raise ValueError(
            f"Invalid ProductionTask status transition: {current} -> {target_status}"
        )

    task.status = target_status
    return task


def schedule_task(task):
    """Create a Runtime Job from a ProductionTask.

    This layer only orchestrates task handoff. Provider execution remains
    inside existing Runtime/Provider implementations.
    """

    transition_task(task, "queued")
    transition_task(task, "scheduled")

    job_type = "github_runtime" if task.provider == "github" else "ai_runtime"

    runtime_job = create_job(
        {
            "task_id": task.id,
            "job_type": job_type,
            "provider": task.provider,
            "input": str(
                {
                    "objective": task.objective,
                    "template": task.template,
                    "parameters": task.parameters,
                    "resources": task.resources,
                }
            ),
        }
    )

    return runtime_job
