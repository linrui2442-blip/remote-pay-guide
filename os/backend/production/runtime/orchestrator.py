from production.providers import get_provider
from production.runtime.manager import get_job, get_latest_job_for_task
from production.runtime.worker import ProductionRuntimeWorker
from production.tasks.execution import require_execution_ready
from production.tasks.manager import get_task
from production.tasks.scheduler import schedule_task


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
