import re
from datetime import date, timedelta

from analytics.manager import get_latest_metrics, get_metrics
from assets.manager import get_asset
from data.growth import get_content_funnel
from data.tracking import get_history_summaries, get_tracking_records
from publish.manager import get_publish_tasks


VALID_SCOPES = {"active", "historical", "archived", "all"}
DEFAULT_SELECTED_METRICS = (
    "views",
    "watch_time",
    "average_view_percentage",
    "likes",
    "comments",
    "shares",
    "referral_clicks",
    "conversions",
    "conversion_value",
)
METRIC_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
DATE_RANGES = {"7d": 7, "28d": 28, "90d": 90}
VALID_DATE_RANGES = {*DATE_RANGES, "lifetime", "custom"}
ADDITIVE_METRICS = {
    "impressions", "views", "clicks", "likes", "comments", "watch_time", "shares",
}
WEIGHTED_METRICS = {"ctr", "average_view_duration", "retention", "average_view_percentage"}
WEIGHT_FIELDS = {"ctr": "impressions", "average_view_duration": "views", "retention": "views", "average_view_percentage": "views"}


def _normalize(value):
    return str(value or "").strip().lower()


def _normalize_metrics(metrics):
    if metrics is None:
        return list(DEFAULT_SELECTED_METRICS)
    if isinstance(metrics, str):
        values = [item.strip() for item in metrics.split(",") if item.strip()]
    else:
        values = [str(item).strip() for item in metrics if str(item).strip()]
    result = []
    for metric in values:
        if not METRIC_NAME_RE.match(metric):
            raise ValueError(f"invalid metric name: {metric}")
        if metric not in result:
            result.append(metric)
    return result or list(DEFAULT_SELECTED_METRICS)


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


def _metric_map(metric, *, referral_clicks=0, conversions=0, conversion_value=0):
    values = dict(metric.get("metrics") or {})
    # Data Center exposes the cross-platform name used by the query/UI while
    # preserving the legacy storage key (retention) in the raw metric payload.
    values["average_view_percentage"] = metric.get("retention")
    values["referral_clicks"] = int(referral_clicks or 0)
    values["conversions"] = int(conversions or 0)
    values["conversion_value"] = float(conversion_value or 0)
    return values


def _current_rows(
    account_id=None,
    platform=None,
    scope="active",
    metric_records=None,
    growth_start=None,
    growth_end=None,
):
    normalized_platform = _normalize(platform) or None
    publish_index = _publish_index()
    metrics = get_latest_metrics() if metric_records is None else metric_records

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
        funnel = get_content_funnel(content_id, growth_start, growth_end)
        intent_by_type = funnel.get("intent", {}).get("by_type", {})
        conversion = funnel.get("conversion", {})
        referral_clicks = int(
            intent_by_type.get("binance_referral_click", 0) or 0
        )
        conversions = int(conversion.get("total", 0) or 0)
        conversion_value = float(conversion.get("value", 0) or 0)
        metric_values = _metric_map(
            metric,
            referral_clicks=referral_clicks,
            conversions=conversions,
            conversion_value=conversion_value,
        )

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
                "snapshot_selection": metric.get("snapshot_selection"),
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
                "referral_clicks": referral_clicks,
                "conversions": conversions,
                "conversion_value": conversion_value,
                "metrics": metric_values,
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
            metric_values = {
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
                    "views": metric_values["views"],
                    "watch_time": metric_values["watch_time"],
                    "average_view_duration": metric_values["average_view_duration"],
                    "average_view_percentage": metric_values["average_view_percentage"],
                    "likes": metric_values["likes"],
                    "comments": metric_values["comments"],
                    "shares": metric_values["shares"],
                    "impressions": 0,
                    "clicks": 0,
                    "ctr": None,
                    "referral_clicks": metric_values["referral_clicks"],
                    "conversions": metric_values["conversions"],
                    "conversion_value": metric_values["conversion_value"],
                    "metrics": metric_values,
                }
            )
    return rows


def _metric_value(row, field):
    if field in row and row.get(field) is not None:
        return row.get(field)
    return (row.get("metrics") or {}).get(field)


def _sort_value(row, field):
    value = _metric_value(row, field)
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


def _decorate_selected_metrics(rows, selected_metrics):
    for row in rows:
        row["metric_values"] = {
            metric: _metric_value(row, metric)
            for metric in selected_metrics
        }
    return rows


def _parse_date(value, name):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD)") from None


def _resolve_period(date_range, start_date=None, end_date=None):
    normalized = _normalize(date_range)
    if normalized not in VALID_DATE_RANGES:
        raise ValueError("date_range must be one of 7d, 28d, 90d, lifetime, custom")
    if normalized == "lifetime":
        if start_date or end_date:
            raise ValueError("start_date/end_date are not supported with date_range=lifetime")
        return {"date_range": normalized, "start_date": None, "end_date": None, "days": None}
    resolved_end = _parse_date(end_date, "end_date") if end_date else date.today() - timedelta(days=1)
    if normalized == "custom":
        if not start_date or not end_date:
            raise ValueError("custom date_range requires start_date and end_date")
        resolved_start = _parse_date(start_date, "start_date")
    else:
        resolved_start = resolved_end - timedelta(days=DATE_RANGES[normalized] - 1)
        if start_date and _parse_date(start_date, "start_date") != resolved_start:
            raise ValueError(f"start_date does not match date_range={normalized}")
    if resolved_start > resolved_end:
        raise ValueError("start_date must be on or before end_date")
    return {"date_range": normalized, "start_date": resolved_start.isoformat(), "end_date": resolved_end.isoformat(), "days": (resolved_end - resolved_start).days + 1}


def _previous_period(period):
    if period["days"] is None:
        return None
    current_start = _parse_date(period["start_date"], "start_date")
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period["days"] - 1)
    return {"date_range": "previous_period", "start_date": previous_start.isoformat(), "end_date": previous_end.isoformat(), "days": period["days"]}


def _identity(metric):
    return (metric.get("video_id"), _normalize(metric.get("platform")), metric.get("account_id"))


def _latest_by(records, key):
    selected = {}
    for record in records:
        record_key = key(record)
        current = selected.get(record_key)
        rank = (str(record.get("collected_at") or ""), int(record.get("id") or 0))
        current_rank = (str(current.get("collected_at") or ""), int(current.get("id") or 0)) if current else None
        if current is None or rank > current_rank:
            selected[record_key] = record
    return list(selected.values())


def _metric_number(record, name):
    value = record.get("retention") if name == "average_view_percentage" else _metric_value(record, name)
    return value if isinstance(value, (int, float)) else None


def _weighted_value(values, name):
    weight_field = WEIGHT_FIELDS[name]
    weights = [max(float(_metric_number(item, weight_field) or 0), 0) for item, _ in values]
    return sum(value * weight for (_, value), weight in zip(values, weights)) / sum(weights) if sum(weights) else values[-1][1]


def _aggregate_snapshots(records, start_date, end_date):
    exact = _latest_by(
        [record for record in records if record.get("period_start") == start_date and record.get("period_end") == end_date],
        _identity,
    )
    exact_keys = {_identity(item) for item in exact}
    daily = _latest_by(
        [record for record in records if record.get("period_start") == record.get("period_end") and record.get("period_start") and start_date <= record["period_start"] <= end_date and _identity(record) not in exact_keys],
        lambda item: (_identity(item), item.get("period_start")),
    )
    grouped = {}
    for item in daily:
        grouped.setdefault(_identity(item), []).append(item)
    aggregated = list(exact)
    for items in grouped.values():
        base = dict(items[-1])
        payload = {}
        names = {name for item in items for name in (item.get("metrics") or {})} | ADDITIVE_METRICS | WEIGHTED_METRICS
        for name in names:
            values = [(item, _metric_number(item, name)) for item in items]
            values = [(item, value) for item, value in values if value is not None]
            if name in ADDITIVE_METRICS:
                payload[name] = sum(value for _, value in values)
            elif name in WEIGHTED_METRICS and values:
                payload[name] = _weighted_value(values, name)
        for name in ADDITIVE_METRICS:
            base[name] = payload.get(name, 0)
        base["average_view_duration"] = payload.get("average_view_duration")
        base["retention"] = payload.get("retention", payload.get("average_view_percentage"))
        base["ctr"] = payload.get("ctr")
        base["metrics"] = payload
        base["period_start"] = start_date
        base["period_end"] = end_date
        base["snapshot_selection"] = "daily_rollup"
        aggregated.append(base)
    for item in aggregated:
        item.setdefault("snapshot_selection", "exact_window_latest")
    return aggregated


def _period_metric_records(period, records):
    if period["days"] is None:
        selected = _latest_by(records, _identity)
        for item in selected:
            item.setdefault("snapshot_selection", "latest_available_window")
        return selected
    return _aggregate_snapshots(records, period["start_date"], period["end_date"])


def _daily_time_series(records, period, selected_metrics):
    if period["days"] is None:
        return []
    daily = _latest_by(
        [record for record in records if record.get("period_start") == record.get("period_end") and record.get("period_start") and period["start_date"] <= record["period_start"] <= period["end_date"]],
        lambda item: (_identity(item), item.get("period_start")),
    )
    points = []
    cursor = _parse_date(period["start_date"], "start_date")
    end = _parse_date(period["end_date"], "end_date")
    while cursor <= end:
        day = cursor.isoformat()
        day_records = [item for item in daily if item.get("period_start") == day]
        if not day_records:
            points.append({
                "date": day,
                "has_snapshot": False,
                "metric_values": {name: None for name in selected_metrics},
                "snapshot_count": 0,
            })
            cursor += timedelta(days=1)
            continue
        values = {}
        for name in selected_metrics:
            metric_values = [(item, _metric_number(item, name)) for item in day_records]
            metric_values = [(item, value) for item, value in metric_values if value is not None]
            if name in ADDITIVE_METRICS:
                values[name] = sum(value for _, value in metric_values)
            elif name in WEIGHTED_METRICS and metric_values:
                values[name] = _weighted_value(metric_values, name)
            else:
                values[name] = None
        points.append({"date": day, "has_snapshot": True, "metric_values": values, "snapshot_count": len(day_records)})
        cursor += timedelta(days=1)
    return points


def _comparison(current, previous, selected_metrics):
    result = {}
    summary_names = {"views": "total_views", "watch_time": "total_watch_time"}
    for name in selected_metrics:
        key = summary_names.get(name, name)
        current_value = current.get(key)
        previous_value = previous.get(key)
        if not isinstance(current_value, (int, float)) or not isinstance(previous_value, (int, float)):
            result[name] = {"current": current_value, "previous": previous_value, "change": None, "change_percent": None}
            continue
        change = current_value - previous_value
        result[name] = {"current": current_value, "previous": previous_value, "change": change, "change_percent": (change / previous_value * 100) if previous_value else None}
    return result


def query_data_center(
    *,
    account_id=None,
    platform=None,
    scope="active",
    metrics=None,
    sort_by="views",
    sort_direction="desc",
    limit=100,
    date_range=None,
    start_date=None,
    end_date=None,
    compare_previous_period=False,
    interval=None,
):
    normalized_scope = _normalize(scope) or "active"
    if normalized_scope not in VALID_SCOPES:
        raise ValueError(f"unsupported scope: {scope}")
    selected_metrics = _normalize_metrics(metrics)
    if sort_by != "published_at" and not METRIC_NAME_RE.match(str(sort_by or "")):
        raise ValueError(f"invalid sort field: {sort_by}")

    v2_requested = bool(date_range or start_date or end_date or compare_previous_period or interval)
    period = _resolve_period(date_range or "custom", start_date, end_date) if v2_requested else None
    if period and (_normalize(interval) or "daily") != "daily":
        raise ValueError("interval currently supports daily only")
    if period and normalized_scope != "active":
        raise ValueError("Query V2 time ranges currently support scope=active only")

    metric_history = get_metrics() if period else None
    filtered_metrics = metric_history
    if filtered_metrics is not None:
        if account_id is not None:
            filtered_metrics = [item for item in filtered_metrics if item.get("account_id") == account_id]
        if _normalize(platform):
            filtered_metrics = [item for item in filtered_metrics if _normalize(item.get("platform")) == _normalize(platform)]
        filtered_metrics = _period_metric_records(period, filtered_metrics)

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
            metric_records=filtered_metrics,
            growth_start=period and period["start_date"],
            growth_end=period and period["end_date"],
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
    limited = _decorate_selected_metrics(rows[:limit], selected_metrics)
    metric_catalog = sorted(
        {
            metric_name
            for row in rows
            for metric_name in (row.get("metrics") or {}).keys()
        }
    )

    result = {
        "filters": {
            "account_id": account_id,
            "platform": _normalize(platform) or None,
            "scope": normalized_scope,
            "metrics": selected_metrics,
            "sort_by": sort_by,
            "sort_direction": "desc" if reverse else "asc",
            "limit": limit,
        },
        "metric_catalog": metric_catalog,
        "summary": _summary(rows),
        "returned": len(limited),
        "total_matching": len(rows),
        "rows": limited,
    }
    if not period:
        return result

    result["query_version"] = "v2"
    result["filters"].update({
        "date_range": period["date_range"],
        "start_date": period["start_date"],
        "end_date": period["end_date"],
        "compare_previous_period": bool(compare_previous_period),
        "interval": "daily",
    })
    result["period"] = period
    trend_source = metric_history or []
    if account_id is not None:
        trend_source = [item for item in trend_source if item.get("account_id") == account_id]
    if _normalize(platform):
        trend_source = [item for item in trend_source if _normalize(item.get("platform")) == _normalize(platform)]
    points = _daily_time_series(trend_source, period, selected_metrics)
    result["time_series"] = {"interval": "daily", "available": any(point["snapshot_count"] for point in points), "points": points}
    result["snapshot_semantics"] = {
        "storage": "window_aggregate_snapshots",
        "selection": "latest exact-window snapshot per video/platform/account; otherwise de-duplicated daily rollup",
        "overlapping_windows_summed": False,
        "trend_requires_daily_snapshots": True,
        "missing_calendar_dates": "Calendar dates without true daily snapshots are returned only as gaps with null metric values; they are never synthetic zero Analytics points.",
        "period_aggregate_metrics": sorted(ADDITIVE_METRICS | WEIGHTED_METRICS),
        "trend_metrics": sorted(ADDITIVE_METRICS | WEIGHTED_METRICS),
        "provider_specific_metrics": "trend only when numeric daily snapshots exist; never inferred from overlapping windows",
        "growth_events": "referral/intent/conversion aggregates use occurred_at inside the inclusive period; daily growth trend is not included in phase 1",
        "historical_scope": "time ranges are unavailable for compact historical/archive summaries in phase 1",
    }
    if compare_previous_period:
        previous = _previous_period(period)
        if previous is None:
            raise ValueError("compare_previous_period is not supported for lifetime")
        previous_records = _period_metric_records(previous, trend_source)
        previous_rows = _current_rows(
            account_id=account_id,
            platform=platform,
            scope=normalized_scope,
            metric_records=previous_records,
            growth_start=previous["start_date"],
            growth_end=previous["end_date"],
        ) if normalized_scope not in {"historical", "archived"} else []
        previous_summary = _summary(previous_rows)
        result["comparison"] = {"period": previous, "summary": previous_summary, "metrics": _comparison(result["summary"], previous_summary, selected_metrics)}
    else:
        result["comparison"] = None
    return result
