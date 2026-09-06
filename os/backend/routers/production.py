from dataclasses import asdict

from fastapi import APIRouter

from production.tasks.manager import create_task, get_task, get_tasks
from production.tasks.models import ProductionTask
from production.tasks.scheduler import schedule_task
from production.providers import production_provider_registry

router = APIRouter()


@router.post('/production/tasks')
def create_production(task: ProductionTask):
    return asdict(create_task(task))


@router.get('/production/tasks')
def production_tasks():
    return [asdict(task) for task in get_tasks()]


@router.get('/production/tasks/{task_id}')
def production_task(task_id: int):
    task = get_task(task_id)
    return asdict(task) if task else None


@router.post('/production/tasks/{task_id}/run')
def run_production(task_id: int):
    task = get_task(task_id)
    if task is None:
        return {'status': 'not_found'}
    return schedule_task(task)


@router.get('/production/status')
def production_status():
    return {'status': 'ready', 'providers': list(production_provider_registry.keys())}


@router.get('/production/providers')
def production_providers():
    return [
        {
            'name': name,
            'status': 'registered',
        }
        for name in production_provider_registry.keys()
    ]
