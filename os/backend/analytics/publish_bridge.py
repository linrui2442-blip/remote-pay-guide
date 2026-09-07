from analytics.collector import AnalyticsCollectionNotReady, AnalyticsCollector
from analytics.errors import AnalyticsNoData
from data.sync_state import (
    mark_sync_failure,
    mark_sync_partial,
    mark_sync_started,
    mark_sync_success,
)
from data.tracking import DEFAULT_ACTIVE_LIMIT, get_active_publish_tasks
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


def _analytics_cursor(collected, account_metric=None, fallback=None):
    candidates = []
    if account_metric:
        cursor = account_metric.get("period_end") or account_metric.get("collected_at")
        if cursor:
            candidates.append(str(cursor))
    for item in collected:
        metric = item.get("metric") or {}
        cursor = metric.get("period_end") or metric.get("collected_at")
        if cursor:
            candidates.append(str(cursor))
    return max(candidates) if candidates else fallback


def collect_account_publish_metrics(
    account_id,
    *,
    platform=None,
    collector=None,
    start_date=None,
    end_date=None,
    active_limit=DEFAULT_ACTIVE_LIMIT,
):
    """Collect account analytics plus the active content tracking window.

    The default content policy tracks the newest 10 published items per bound
    platform account, plus manually pinned items. Content that leaves the active
    window becomes historical and keeps its stored metrics/lifecycle summary.

    Providers that expose account/channel Analytics may also collect one account
    snapshot in the same batch. Test doubles and future adapters can omit the
    optional ``collect_account`` method until that capability is implemented.
    """
    normalized_platform = (platform or "").strip().lower() or None
    if not normalized_platform:
        raise AnalyticsCollectionNotReady(
            "account-level analytics sync requires a platform"
        )

    mark_sync_started(account_id, normalized_platform, "analytics")
    try:
        tasks = get_active_publish_tasks(
            account_id,
            normalized_platform,
            active_limit=active_limit,
        )

        active_collector = collector or AnalyticsCollector()
        collected = []
        failures = []
        no_data = []
        account_metric = None
        account_failure = None
        account_no_data = False

        collect_account = getattr(active_collector, "collect_account", None)
        if callable(collect_account):
            try:
                account_metric = collect_account(
                    normalized_platform,
                    account_id=account_id,
                    start_date=start_date,
                    end_date=end_date,
                )
            except AnalyticsNoData:
                account_no_data = True
            except Exception as exc:
                account_failure = str(exc)

        for task in tasks:
            try:
                metric = collect_publish_task_metrics(
                    task["id"],
                    collector=active_collector,
                    start_date=start_date,
                    end_date=end_date,
                )
                collected.append(
                    {
                        "task_id": task["id"],
                        "video_id": task.get("platform_video_id"),
                        "metric": metric,
                    }
                )
            except AnalyticsNoData:
                no_data.append(
                    {
                        "task_id": task["id"],
                        "video_id": task.get("platform_video_id"),
                    }
                )
            except Exception as exc:
                failures.append(
                    {
                        "task_id": task["id"],
                        "video_id": task.get("platform_video_id"),
                        "error": str(exc),
                    }
                )

        cursor = _analytics_cursor(
            collected,
            account_metric=account_metric,
            fallback=end_date,
        )
        failure_count = len(failures) + (1 if account_failure else 0)
        success_count = len(collected) + len(no_data) + (1 if account_metric else 0) + int(account_no_data)
        total_operations = len(tasks) + (1 if callable(collect_account) else 0)

        if failure_count and success_count:
            sync_state = mark_sync_partial(
                account_id,
                normalized_platform,
                "analytics",
                cursor=cursor,
                error=f"{failure_count} of {total_operations} analytics operations failed",
            )
        elif failure_count:
            error = f"all {failure_count} analytics operations failed"
            sync_state = mark_sync_failure(
                account_id,
                normalized_platform,
                "analytics",
                error,
            )
        else:
            sync_state = mark_sync_success(
                account_id,
                normalized_platform,
                "analytics",
                cursor=cursor,
            )

        return {
            "account_id": account_id,
            "platform": normalized_platform,
            "tracking_policy": "latest_plus_pinned",
            "active_limit": active_limit,
            "found": len(tasks),
            "collected": len(collected),
            "failed": len(failures),
            "no_data": len(no_data),
            "no_data_results": no_data,
            "account_metric": account_metric,
            "account_failure": account_failure,
            "account_no_data": account_no_data,
            "analytics_cursor": cursor,
            "results": collected,
            "failures": failures,
            "sync_state": sync_state,
        }
    except Exception as exc:
        mark_sync_failure(account_id, normalized_platform, "analytics", exc)
        raise
