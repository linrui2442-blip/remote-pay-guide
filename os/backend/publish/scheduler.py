from datetime import datetime, timezone


class PublishScheduler:
    def __init__(self, queue):
        self.queue = queue

    def check(self, tasks):
        now = datetime.now(timezone.utc)
        scheduled = []

        for task in tasks:
            if task.get('status') != 'pending' or not task.get('scheduled_time'):
                continue
            try:
                due = datetime.fromisoformat(str(task['scheduled_time']).replace('Z', '+00:00'))
                if due.tzinfo is None:
                    due = due.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
            if due <= now:
                self.queue.add_task(task["id"])
                scheduled.append(task["id"])

        return scheduled

    def status(self):
        return {"status": "ready"}
