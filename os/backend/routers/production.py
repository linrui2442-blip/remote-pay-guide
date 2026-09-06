from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from production.providers import production_provider_registry
from production.tasks.execution import get_execution_readiness
from production.tasks.manager import create_task, get_task, get_tasks
from production.tasks.models import ProductionTask
from production.tasks.scheduler import schedule_task

router = APIRouter()


def _serialize_task(task):
    data = asdict(task)
    data['execution'] = get_execution_readiness(task)
    return data


def _provider_runtime_status(name, provider):
    if hasattr(provider, 'get_provider_status'):
        try:
            status = provider.get_provider_status()
        except Exception as exc:
            status = {'status': 'error', 'error': str(exc)}
    elif hasattr(provider, 'get_status'):
        try:
            status = provider.get_status()
        except TypeError:
            status = {'status': 'registered'}
        except Exception as exc:
            status = {'status': 'error', 'error': str(exc)}
    else:
        status = {'status': 'registered'}

    if not isinstance(status, dict):
        status = {'status': str(status)}
    return {'name': name, **status}


@router.post('/production/tasks')
def create_production(task: ProductionTask):
    return _serialize_task(create_task(task))


@router.get('/production/tasks')
def production_tasks():
    return [_serialize_task(task) for task in get_tasks()]


@router.get('/production/tasks/{task_id}')
def production_task(task_id: int):
    task = get_task(task_id)
    return _serialize_task(task) if task else None


@router.get('/production/tasks/{task_id}/readiness')
def production_task_readiness(task_id: int):
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail='production task not found')
    return get_execution_readiness(task)


@router.post('/production/tasks/{task_id}/run')
def run_production(task_id: int):
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail='production task not found')
    try:
        return schedule_task(task)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/production/status')
def production_status():
    providers = [
        _provider_runtime_status(name, provider)
        for name, provider in production_provider_registry.items()
    ]
    return {
        'status': 'ready',
        'providers': providers,
    }


@router.get('/production/providers')
def production_providers():
    return [
        _provider_runtime_status(name, provider)
        for name, provider in production_provider_registry.items()
    ]
