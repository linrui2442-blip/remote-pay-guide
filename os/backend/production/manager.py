"""Compatibility facade over the canonical ProductionTask manager.

All Production Center task reads/writes use production.tasks.manager as the
single SQLite source of truth.
"""

from dataclasses import asdict

from production.tasks.manager import (
    create_task,
    get_task,
    get_tasks,
    update_task_status,
)


def create_production_task(task):
    return asdict(create_task(task))


def get_production_tasks():
    return [asdict(task) for task in get_tasks()]


def get_production_task(task_id):
    task = get_task(task_id)
    return asdict(task) if task else None


def update_production_status(task_id, status):
    task = update_task_status(task_id, status)
    return asdict(task) if task else None
