from analytics.collector import AnalyticsCollectionNotReady, AnalyticsCollector
from publish.manager import get_publish_task


class PublishAnalyticsTaskNotFound(LookupError):
    pass


def collect_publish_task_metrics(
    task_id,
    *,
    collector=None,
    start_date=None,
    end_date=None,
):
    """Collect analytics for one completed Publish Center task.

    Publish Center remains the source of truth for the platform video id and
    account binding. The Data Center collector receives those identifiers
    without duplicating publish metadata or introducing platform-specific
    fields into the analytics storage model.
    """
    task = get_publish_task(task_id)
    if not task:
        raise PublishAnalyticsTaskNotFound(f"publish task {task_id} was not found")

    status = (task.get("status") or "").strip().lower()
    if status != "published":
        raise AnalyticsCollectionNotReady(
            f"publish task {task_id} is not published yet"
        )

    platform = (task.get("platform") or "").strip().lower()
    if not platform:
        raise AnalyticsCollectionNotReady(
            f"publish task {task_id} does not have a platform"
        )

    platform_video_id = task.get("platform_video_id")
    if not platform_video_id:
        raise AnalyticsCollectionNotReady(
            f"publish task {task_id} does not have a platform video id"
        )

    account_id = task.get("account_id")
    if account_id is None:
        raise AnalyticsCollectionNotReady(
            f"publish task {task_id} does not have an account_id"
        )

    content_id = task.get("video_id") or task.get("asset_id") or platform_video_id
    active_collector = collector or AnalyticsCollector()

    return active_collector.collect(
        platform_video_id,
        platform,
        account_id=account_id,
        content_id=content_id,
        start_date=start_date,
        end_date=end_date,
    )
