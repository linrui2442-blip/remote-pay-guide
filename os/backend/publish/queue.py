class PublishQueue:
    def __init__(self):
        self.tasks = []

    def add_task(self, publish_task_id):
        self.tasks.append(publish_task_id)
        return publish_task_id

    def get_pending_tasks(self):
        return list(self.tasks)

    def remove_task(self, publish_task_id):
        if publish_task_id in self.tasks:
            self.tasks.remove(publish_task_id)
            return True
        return False
