"""Compatibility facade over the canonical ProductionTask manager.

All Production Center task reads/writes use production.tasks.manager as the
single SQLite source of truth.
"""

from dataclasses import asdict

from production.tasks.manager import create_task, get_task, get_tasks
from production.tasks.scheduler import transition_task


def create_production_task(task):
    return asdict(create_task(task))


def get_production_tasks():
    return [asdict(task) for task in get_tasks()]


def get_production_task(task_id):
    task = get_task(task_id)
    return asdict(task) if task else None


def update_production_status(task_id, status):
    task = get_task(task_id)
    if task is None:
        return None
    return asdict(transition_task(task, status))
