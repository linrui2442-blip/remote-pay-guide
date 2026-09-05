from publish.adapters.youtube import YouTubeAdapter
from publish.manager import get_publish_task, update_publish_status


class PublishWorker:
    def __init__(self, queue):
        self.queue = queue
        self.adapters = {
            "youtube": YouTubeAdapter()
        }
        self.adapters["youtube"].initialize()

    def run_once(self):
        processed = 0

        for task_id in self.queue.get_pending_tasks():
            task = get_publish_task(task_id)
            if not task:
                continue

            adapter = self.adapters.get(task["platform"])
            if not adapter:
                update_publish_status(task_id, "failed")
                continue

            update_publish_status(task_id, "publishing")
            result = adapter.publish_video(
                {"video_id": task["video_id"]},
                task.get("account_id")
            )

            if result.get("status") == "simulated_upload":
                update_publish_status(task_id, "published")
            else:
                update_publish_status(task_id, "failed")

            self.queue.remove_task(task_id)
            processed += 1

        return {
            "processed": processed,
            "status": "completed"
        }
