from assets.manager import get_asset, get_asset_by_asset_id
from publish.manager import get_publish_task, update_publish_status
from publish.registry import get_adapter


class PublishWorker:
    def __init__(self, queue):
        self.queue = queue

    def _resolve_asset(self, task):
        asset_id = task.get("asset_id")
        if asset_id:
            asset = get_asset_by_asset_id(asset_id)
            if asset:
                return asset

        video_id = task.get("video_id")
        if video_id:
            asset = get_asset(video_id)
            if asset:
                return asset
            return {
                "asset_id": None,
                "video_id": video_id,
                "asset_url": None,
                "file_path": None,
                "location": video_id,
            }
        return None

    def run_once(self):
        processed = 0

        for task_id in self.queue.get_pending_tasks():
            task = get_publish_task(task_id)
            if not task:
                continue

            adapter = get_adapter(task.get("platform"))
            if not adapter:
                update_publish_status(task_id, "failed", error_message="unsupported platform")
                self.queue.remove_task(task_id)
                processed += 1
                continue

            asset = self._resolve_asset(task)
            if not asset:
                update_publish_status(task_id, "failed", error_message="video asset not found")
                self.queue.remove_task(task_id)
                processed += 1
                continue

            update_publish_status(task_id, "publishing")
            account_id = task.get("account_id")

            try:
                if task.get("platform") == "youtube":
                    video_reference = asset.get("file_path") or asset.get("asset_url") or asset.get("location")
                    result = adapter.publish_video(
                        asset,
                        account_id,
                        video_path=video_reference,
                        title=asset.get("video_id") or task.get("video_id") or task.get("asset_id"),
                    )
                else:
                    result = adapter.publish_video(asset, account_id)
            except Exception as exc:
                result = {"status": "failed", "error": str(exc)}

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

        return {"processed": processed, "status": "completed"}
