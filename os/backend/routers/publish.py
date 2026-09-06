from fastapi import APIRouter, HTTPException

from publish.manager import get_publish_task, get_publish_tasks
from publish.registry import get_registry_status


router = APIRouter()


@router.get('/publish/tasks')
def publish_tasks():
    return get_publish_tasks()


@router.get('/publish/tasks/{task_id}')
def publish_task(task_id: int):
    task = get_publish_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='publish task not found')
    return task


@router.get('/publish/platforms')
def publish_platforms():
    """Return runtime publish adapters with Data Center capability metadata."""
    return get_registry_status()
