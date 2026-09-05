from datetime import datetime


class PublishScheduler:
    def __init__(self, queue):
        self.queue = queue

    def check(self, tasks):
        now = datetime.utcnow().isoformat()
        scheduled = []

        for task in tasks:
            if task.get("scheduled_time") and task["scheduled_time"] <= now:
                self.queue.add_task(task["id"])
                scheduled.append(task["id"])

        return scheduled

    def status(self):
        return {"status": "ready"}
