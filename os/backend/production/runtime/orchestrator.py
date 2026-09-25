from production.providers import get_provider
from production.runtime.manager import get_job, get_latest_job_for_task, get_jobs_for_task, claim_provider_execution, update_execution_metadata
from production.runtime.worker import ProductionRuntimeWorker
from production.tasks.execution import require_execution_ready
from production.tasks.manager import get_task
from production.tasks.scheduler import schedule_task
from production.tasks.scheduler import transition_task
from production.results.manager import create_or_get_result_for_job, get_result_by_job
from production.providers import get_provider
from datetime import datetime, timezone
from intelligence.content_plan_service import _validate_materialized_task


def get_provider_runtime_readiness(provider_name: str):
    provider = get_provider(provider_name)
    if provider is None:
        return {
            'ready': False,
            'provider': provider_name,
            'status': 'missing',
            'reason': 'production provider is not registered',
        }

    try:
        if hasattr(provider, 'get_provider_status'):
            status = provider.get_provider_status()
        elif hasattr(provider, 'get_status'):
            status = provider.get_status()
        else:
            status = {'status': 'registered'}
    except Exception as exc:
        return {
            'ready': False,
            'provider': provider_name,
            'status': 'error',
            'reason': str(exc),
        }

    if not isinstance(status, dict):
        status = {'status': str(status)}

    state = str(status.get('status') or 'registered').strip().lower()
    configured = status.get('configured')
    ready = configured is not False and state not in {
        'error',
        'failed',
        'configuration_required',
        'missing',
    }
    reason = status.get('error') or status.get('reason')
    if not ready and not reason:
        missing = status.get('missing_configuration') or []
        reason = (
            f"missing configuration: {', '.join(str(item) for item in missing)}"
            if missing
            else f'provider runtime is {state}'
        )

    return {
        'ready': ready,
        'provider': provider_name,
        **status,
        'reason': reason,
    }


def execute_production_task(task, *, worker=None):
    """Run the explicit ProductionTask action end-to-end.

    The API's Run action means schedule + invoke Runtime Worker. Validation and
    external provider readiness are checked before lifecycle mutation so a
    missing remote endpoint never strands a task in scheduled state.
    """
    if task is None:
        raise LookupError('production task not found')
    if getattr(task, 'status', None) != 'created':
        raise ValueError(
            f'ProductionTask can only start from created state, got {task.status}'
        )

    execution = require_execution_ready(task)
    provider_readiness = get_provider_runtime_readiness(task.provider)
    if not provider_readiness['ready']:
        reason = provider_readiness.get('reason') or 'provider runtime is not ready'
        raise ValueError(f'{task.provider} provider is not ready: {reason}')

    job = schedule_task(task)
    runtime_worker = worker or ProductionRuntimeWorker()
    result = runtime_worker.run(job)

    return {
        'task_id': task.id,
        'execution': execution,
        'provider_readiness': provider_readiness,
        'runtime_job': get_job(job['id']),
        'result': result,
        'production_task': get_task(task.id),
    }


def refresh_production_task(task, *, worker=None):
    """Poll an active asynchronous ProductionTask without re-submitting it."""
    if task is None:
        raise LookupError('production task not found')

    status = str(getattr(task, 'status', '') or '').strip().lower()
    if status in {'completed', 'failed'}:
        job = get_latest_job_for_task(task.id)
        return {
            'task_id': task.id,
            'status': status,
            'already_terminal': True,
            'runtime_job': job,
            'production_task': get_task(task.id),
        }
    if status not in {'scheduled', 'running'}:
        raise ValueError(
            f'ProductionTask can only be refreshed from scheduled/running state, got {status or "unknown"}'
        )

    job = get_latest_job_for_task(task.id)
    if not job:
        raise LookupError('runtime job not found for production task')

    runtime_worker = worker or ProductionRuntimeWorker()
    result = runtime_worker.poll(job)
    return {
        'task_id': task.id,
        'runtime_job': get_job(job['id']),
        'result': result,
        'production_task': get_task(task.id),
    }


def _fresh_github_claim(plan_id):
    from orchestration.production import _authorization_or_fail
    from intelligence.content_brain import get_plan
    plan = get_plan(plan_id)
    if not plan or plan.get("status") != "materialized":
        raise ValueError("materialized ContentPlan required")
    auth = _authorization_or_fail(plan_id, plan)
    key = f"content-plan:{plan_id}:revision:{plan.get('revision')}"
    task = __import__("production.tasks.manager", fromlist=["get_task_by_idempotency_key"]).get_task_by_idempotency_key(key)
    if not task or task.provider != "github":
        raise ValueError("canonical GitHub ProductionTask required")
    if not task.parameters.get("production_routing") or task.parameters["production_routing"].get("selected_provider") != "github":
        raise ValueError("trusted GitHub route required")
    _validate_materialized_task(task, plan_id, plan.get("revision"), key)
    jobs = get_jobs_for_task(task.id)
    if len(jobs) != 1:
        raise ValueError("exactly one canonical RuntimeJob required")
    job = jobs[0]
    if job.get("provider") != "github" or job.get("job_type") != "github_runtime":
        raise ValueError("GitHub RuntimeJob binding mismatch")
    return plan, auth, task, job


def execute_authorized_claimed_github_runtime(plan_id, *, provider=None, client=None, before_post=None):
    """Execute one already-claimed GitHub RuntimeJob with durable at-most-once dispatch."""
    plan, auth, task, job = _fresh_github_claim(plan_id)
    provider = provider or get_provider("github")
    if provider is None or not hasattr(provider, "submit_job"):
        raise ValueError("GitHub provider submission primitive unavailable")
    metadata = {}
    raw_metadata = job.get("execution_metadata")
    if raw_metadata:
        import json
        try: metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata
        except Exception: metadata = {}
    if job.get("execution_state") in {"submitted", "running", "ambiguous_dispatch", "dispatch_intent"} and not metadata.get("github_run_id"):
        from production.providers.github_monitor import GitHubRunMonitor
        monitor = GitHubRunMonitor(client or getattr(provider, "client", None))
        try:
            recovered = monitor.discover_run(
                metadata.get("workflow") or task.workflow.rsplit("/", 1)[-1],
                metadata.get("branch") or task.branch,
                metadata.get("pre_dispatch_run_ids") or [],
                metadata.get("dispatch_started_at"),
                max_attempts=1,
                poll_interval=0,
            )
            metadata["github_run_id"] = recovered.get("id")
            metadata["github_run_url"] = recovered.get("html_url")
            update_execution_metadata(job["id"], metadata, state="submitted")
        except Exception as exc:
            raise ValueError("dispatch intent exists without uniquely recoverable run; review required") from exc
    if not metadata.get("github_run_id"):
        from production.providers.github_monitor import GitHubRunMonitor
        monitor = GitHubRunMonitor(client or getattr(provider, "client", None))
        intent = {"runtime_job_id": job["id"], "workflow": task.workflow, "branch": task.branch, "dispatch_started_at": datetime.now(timezone.utc).isoformat(), "pre_dispatch_run_ids": sorted(monitor.snapshot_run_ids(task.workflow.rsplit("/",1)[-1], task.branch)), "execution_state": "dispatch_intent", "provider": "github"}
        if not claim_provider_execution(job["id"], intent):
            latest = get_job(job["id"])
            raise ValueError("RuntimeJob execution already claimed")
        if before_post:
            before_post()
        try:
            submitted = provider.submit_job(get_job(job["id"]))
            output = submitted.get("output") or {}
            output["g4b_no_asset_binding"] = True
            metadata.update(intent)
            metadata.update({"github_run_id": output.get("github_run_id"), "github_run_url": output.get("github_run_url"), "workflow": output.get("workflow"), "branch": output.get("branch")})
            if not metadata.get("github_run_id"):
                raise ValueError("GitHub run identity was not discovered")
            update_execution_metadata(job["id"], metadata, state="submitted")
        except Exception as exc:
            metadata.update(intent)
            update_execution_metadata(job["id"], metadata, state="ambiguous_dispatch")
            raise RuntimeError("GitHub dispatch failed or became ambiguous") from exc
    else:
        output = {"github_run_id": metadata.get("github_run_id"), "github_run_url": metadata.get("github_run_url"), "workflow": metadata.get("workflow") or task.workflow.rsplit("/",1)[-1], "branch": metadata.get("branch") or task.branch, "content_id": task.parameters.get("content_id")}
    if task.status == "scheduled":
        task = transition_task(task, "running")
    result = create_or_get_result_for_job({"runtime_job_id": job["id"], "provider": "github", "status": "submitted", "video_id": task.parameters.get("content_id"), "output": output})
    return {"authorization": auth, "production_task": task, "runtime_job": get_job(job["id"]), "production_result": result, "status": result.get("status")}


def refresh_authorized_github_runtime(plan_id, *, provider=None, client=None):
    plan, auth, task, job = _fresh_github_claim(plan_id)
    result = get_result_by_job(job["id"])
    if not result:
        return execute_authorized_claimed_github_runtime(plan_id, provider=provider, client=client)
    worker = ProductionRuntimeWorker()
    try:
        refreshed = worker.poll(job, provider_override=provider or get_provider("github"))
    except Exception as exc:
        current = get_result_by_job(job["id"])
        if current and current.get("status") == "running":
            return {"authorization": auth, "production_task": task, "runtime_job": get_job(job["id"]), "production_result": current, "status": "running", "recovery_error": "promotion or provider completion is pending recovery"}
        raise
    return {"authorization": auth, "production_task": task, "runtime_job": get_job(job["id"]), "production_result": refreshed.get("production_result"), "status": refreshed.get("status")}
