from fastapi import APIRouter, HTTPException

from data.manager import get_platform_runtime_capabilities
from publish.manager import get_publish_task, get_publish_tasks
from publish.models import PublishTask
from publish.orchestrator import (
    PublishContractError,
    execute_publish_task,
    get_publish_execution_readiness,
    prepare_publish_task,
)
from publish.registry import get_registry_status


router = APIRouter()


@router.get('/publish/tasks')
def publish_tasks():
    return get_publish_tasks()


@router.post('/publish/tasks')
def create_publish_task_route(task: PublishTask):
    """Validate and persist a PublishTask without uploading anything."""
    try:
        return prepare_publish_task(task)
    except PublishContractError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get('/publish/tasks/{task_id}')
def publish_task(task_id: int):
    task = get_publish_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='publish task not found')
    return task


@router.post('/publish/tasks/{task_id}/run')
def run_publish_task(task_id: int):
    """Run one explicitly requested task; task creation never auto-publishes."""
    if not get_publish_task(task_id):
        raise HTTPException(status_code=404, detail='publish task not found')
    try:
        return execute_publish_task(task_id)
    except PublishContractError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get('/publish/readiness/{platform}')
def publish_readiness(platform: str):
    try:
        return get_publish_execution_readiness(platform)
    except PublishContractError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/publish/platforms')
def publish_platforms():
    """Return publish adapters plus provider-neutral runtime capabilities."""
    result = []
    for item in get_registry_status():
        platform = item.get('platform')
        result.append(
            {
                **item,
                'runtime': get_platform_runtime_capabilities(platform),
            }
        )
    return result
