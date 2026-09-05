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

            adapter = self.adapters.get(task[2] if isinstance(task, tuple) else task.get("platform"))
            if not adapter:
                update_publish_status(task_id, "failed", error_message="unsupported platform")
                continue

            update_publish_status(task_id, "publishing")

            result = adapter.publish_video(
                {"video_id": task[1] if isinstance(task, tuple) else task.get("video_id")},
                task[3] if isinstance(task, tuple) else task.get("account_id"),
                video_path=task[1] if isinstance(task, tuple) else None,
                title=task[1] if isinstance(task, tuple) else None,
            )

            if result.get("status") == "published":
                update_publish_status(
                    task_id,
                    "published",
                    platform_video_id=result.get("video_id"),
                    published_url=result.get("url"),
                )
            else:
                update_publish_status(
                    task_id,
                    "failed",
                    error_message=result.get("error", result.get("status")),
                )

            self.queue.remove_task(task_id)
            processed += 1

        return {
            "processed": processed,
            "status": "completed"
        }
