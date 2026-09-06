from analytics.manager import get_latest_metrics
from assets.manager import get_asset
from data.growth import get_content_funnel
from data.tracking import get_history_summaries, get_tracking_records
from publish.manager import get_publish_tasks


SORTABLE_FIELDS = {
    "published_at",
    "views",
    "watch_time",
    "average_view_duration",
    "average_view_percentage",
    "likes",
    "comments",
    "shares",
    "referral_clicks",
    "conversions",
    "conversion_value",
}
VALID_SCOPES = {"active", "historical", "archived", "all"}


def _normalize(value):
    return str(value or "").strip().lower()


def _publish_index():
    index = {}
    for task in get_publish_tasks():
        platform = _normalize(task.get("platform"))
        platform_video_id = task.get("platform_video_id")
        if not platform or not platform_video_id:
            continue
        key = (platform, str(platform_video_id))
        current = index.get(key)
        if current is None or int(task.get("id") or 0) > int(current.get("id") or 0):
            index[key] = task
    return index


def _tracking_index(account_ids):
    index = {}
    for account_id in account_ids:
        if account_id is None:
            continue
        for record in get_tracking_records(account_id):
            index[
                (
                    account_id,
                    _normalize(record.get("platform")),
                    str(record.get("platform_video_id")),
                )
            ] = record
    return index


def _asset_metadata(video_id):
    asset = get_asset(video_id) if video_id else None
    metadata = (asset or {}).get("metadata") or {}
    return {
        "title": metadata.get("title"),
        "published_at": metadata.get("published_at"),
        "asset": asset,
    }


def _current_rows(account_id=None, platform=None, scope="active"):
    normalized_platform = _normalize(platform) or None
    publish_index = _publish_index()
    metrics = get_latest_metrics()

    account_ids = {
        metric.get("account_id")
        for metric in metrics
        if metric.get("account_id") is not None
    }
    account_ids.update(
        task.get("account_id")
        for task in publish_index.values()
        if task.get("account_id") is not None
    )
    tracking_index = _tracking_index(account_ids)

    rows = []
    for metric in metrics:
        metric_platform = _normalize(metric.get("platform"))
        platform_video_id = str(metric.get("video_id") or "")
        task = publish_index.get((metric_platform, platform_video_id))
        resolved_account_id = metric.get("account_id")
        if resolved_account_id is None and task:
            resolved_account_id = task.get("account_id")

        if account_id is not None and resolved_account_id != account_id:
            continue
        if normalized_platform and metric_platform != normalized_platform:
            continue

        tracking = tracking_index.get(
            (resolved_account_id, metric_platform, platform_video_id)
        )
        tracking_state = (tracking or {}).get("state") or "untracked"
        if scope != "all":
            if scope == "active" and tracking_state not in {"active", "untracked"}:
                continue
            if scope in {"historical", "archived"} and tracking_state != scope:
                continue

        content_id = metric.get("content_id") or metric.get("video_id")
        metadata = _asset_metadata(content_id)
        funnel = get_content_funnel(content_id)
        intent_by_type = funnel.get("intent", {}).get("by_type", {})
        conversion = funnel.get("conversion", {})

        rows.append(
            {
                "content_id": content_id,
                "video_id": metric.get("video_id"),
                "platform_video_id": platform_video_id,
                "account_id": resolved_account_id,
                "platform": metric_platform,
                "title": (
                    (tracking or {}).get("title")
                    or (task or {}).get("title")
                    or metadata.get("title")
                    or platform_video_id
                ),
                "published_at": (
                    (tracking or {}).get("published_at")
                    or metadata.get("published_at")
                    or (task or {}).get("created_at")
                ),
                "tracking_state": tracking_state,
                "pinned": bool((tracking or {}).get("pinned")),
                "period_start": metric.get("period_start"),
                "period_end": metric.get("period_end"),
                "collected_at": metric.get("collected_at"),
                "views": int(metric.get("views") or 0),
                "watch_time": int(metric.get("watch_time") or 0),
                "average_view_duration": metric.get("average_view_duration"),
                "average_view_percentage": metric.get("retention"),
                "likes": int(metric.get("likes") or 0),
                "comments": int(metric.get("comments") or 0),
                "shares": int(metric.get("shares") or 0),
                "impressions": int(metric.get("impressions") or 0),
                "clicks": int(metric.get("clicks") or 0),
                "ctr": metric.get("ctr"),
                "referral_clicks": int(
                    intent_by_type.get("binance_referral_click", 0) or 0
                ),
                "conversions": int(conversion.get("total", 0) or 0),
                "conversion_value": float(conversion.get("value", 0) or 0),
            }
        )
    return rows


def _historical_rows(account_id=None, platform=None, state=None):
    publish_index = _publish_index()
    account_ids = {
        task.get("account_id")
        for task in publish_index.values()
        if task.get("account_id") is not None
    }
    if account_id is not None:
        account_ids = {account_id}

    normalized_platform = _normalize(platform) or None
    normalized_state = _normalize(state) or None
    rows = []
    for current_account_id in account_ids:
        tracking = {
            (
                _normalize(item.get("platform")),
                str(item.get("platform_video_id")),
            ): item
            for item in get_tracking_records(current_account_id, normalized_platform)
        }
        for item in get_history_summaries(current_account_id, normalized_platform):
            key = (_normalize(item.get("platform")), str(item.get("platform_video_id")))
            tracking_item = tracking.get(key) or {}
            tracking_state = tracking_item.get("state") or "historical"
            if normalized_state and tracking_state != normalized_state:
                continue
            rows.append(
                {
                    "content_id": item.get("content_id"),
                    "video_id": item.get("platform_video_id"),
                    "platform_video_id": item.get("platform_video_id"),
                    "account_id": item.get("account_id"),
                    "platform": _normalize(item.get("platform")),
                    "title": item.get("title") or item.get("platform_video_id"),
                    "published_at": item.get("published_at"),
                    "tracking_state": tracking_state,
                    "pinned": bool(tracking_item.get("pinned")),
                    "period_start": None,
                    "period_end": None,
                    "collected_at": item.get("summarized_at"),
                    "views": int(item.get("views") or 0),
                    "watch_time": int(item.get("watch_time") or 0),
                    "average_view_duration": item.get("average_view_duration"),
                    "average_view_percentage": item.get("average_view_percentage"),
                    "likes": int(item.get("likes") or 0),
                    "comments": int(item.get("comments") or 0),
                    "shares": int(item.get("shares") or 0),
                    "impressions": 0,
                    "clicks": 0,
                    "ctr": None,
                    "referral_clicks": int(item.get("referral_clicks") or 0),
                    "conversions": int(item.get("conversions") or 0),
                    "conversion_value": float(item.get("conversion_value") or 0),
                }
            )
    return rows


def _sort_value(row, field):
    value = row.get(field)
    if value is None:
        return -1 if field != "published_at" else ""
    return value


def _summary(rows):
    total_views = sum(row.get("views", 0) for row in rows)
    weighted_retention_numerator = sum(
        (row.get("average_view_percentage") or 0) * max(row.get("views", 0), 0)
        for row in rows
    )
    weighted_retention = (
        weighted_retention_numerator / total_views if total_views > 0 else None
    )
    return {
        "content_count": len(rows),
        "total_views": total_views,
        "total_watch_time": sum(row.get("watch_time", 0) for row in rows),
        "average_view_percentage": weighted_retention,
        "likes": sum(row.get("likes", 0) for row in rows),
        "comments": sum(row.get("comments", 0) for row in rows),
        "shares": sum(row.get("shares", 0) for row in rows),
        "referral_clicks": sum(row.get("referral_clicks", 0) for row in rows),
        "conversions": sum(row.get("conversions", 0) for row in rows),
        "conversion_value": sum(row.get("conversion_value", 0) for row in rows),
    }


def query_data_center(
    *,
    account_id=None,
    platform=None,
    scope="active",
    sort_by="views",
    sort_direction="desc",
    limit=100,
):
    normalized_scope = _normalize(scope) or "active"
    if normalized_scope not in VALID_SCOPES:
        raise ValueError(f"unsupported scope: {scope}")
    if sort_by not in SORTABLE_FIELDS:
        raise ValueError(f"unsupported sort field: {sort_by}")

    if normalized_scope in {"historical", "archived"}:
        rows = _historical_rows(
            account_id=account_id,
            platform=platform,
            state=normalized_scope,
        )
    else:
        rows = _current_rows(
            account_id=account_id,
            platform=platform,
            scope=normalized_scope,
        )
        if normalized_scope == "all":
            current_keys = {
                (row.get("account_id"), row.get("platform"), row.get("platform_video_id"))
                for row in rows
            }
            for row in _historical_rows(account_id=account_id, platform=platform):
                key = (
                    row.get("account_id"),
                    row.get("platform"),
                    row.get("platform_video_id"),
                )
                if key not in current_keys:
                    rows.append(row)

    reverse = _normalize(sort_direction) != "asc"
    rows.sort(key=lambda row: _sort_value(row, sort_by), reverse=reverse)
    limit = max(1, min(int(limit or 100), 1000))
    limited = rows[:limit]

    return {
        "filters": {
            "account_id": account_id,
            "platform": _normalize(platform) or None,
            "scope": normalized_scope,
            "sort_by": sort_by,
            "sort_direction": "desc" if reverse else "asc",
            "limit": limit,
        },
        "summary": _summary(rows),
        "returned": len(limited),
        "total_matching": len(rows),
        "rows": limited,
    }
