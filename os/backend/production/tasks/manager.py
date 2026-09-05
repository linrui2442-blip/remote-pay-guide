from .models import ProductionTask


_tasks = []


def create_task(task: ProductionTask):
    task.validate()
    _tasks.append(task)
    return task


def get_tasks():
    return _tasks


def get_task(task_id):
    for task in _tasks:
        if task.id == task_id:
            return task
    return None
