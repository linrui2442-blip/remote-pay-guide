from fastapi import APIRouter
from production.models import ProductionTask
from production.manager import create_production_task, get_production_tasks, get_production_task
from production.providers import get_provider, production_provider_registry

router = APIRouter()

@router.post('/production/tasks')
def create_production(task: ProductionTask):
    return create_production_task(task)

@router.get('/production/tasks')
def production_tasks():
    return get_production_tasks()

@router.get('/production/tasks/{task_id}')
def production_task(task_id: int):
    return get_production_task(task_id)

@router.post('/production/tasks/{task_id}/run')
def run_production(task_id: int):
    task = get_production_task(task_id)
    provider = get_provider(task['provider']) if task else None
    return {'status':'failed'} if provider is None else provider.run(task)

@router.get('/production/status')
def production_status():
    return {'status':'ready','providers':list(production_provider_registry.keys())}
