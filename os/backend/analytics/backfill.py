from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from accounts.manager import get_account
from analytics.collector import AnalyticsCollector
from analytics.manager import get_account_metrics
from analytics.registry import get_analytics_adapter_registration
from data.sync_state import (
    get_sync_state,
    mark_backfill_failure,
    mark_backfill_progress,
    mark_backfill_started,
    mark_backfill_success,
)


BACKFILL_RANGES = {"7d": 7, "28d": 28, "90d": 90}
MAX_BACKFILL_DAYS = 90
DEFAULT_MAX_REQUESTS = 100
MAX_BACKFILL_REQUESTS = 500
BACKOFF_SECONDS = (300, 900, 3600)


class BackfillValidationError(ValueError):
    pass


class BackfillRetryNotDue(RuntimeError):
    pass


def _utc_datetime(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_date(value, name):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise BackfillValidationError(f"{name} must be an ISO date (YYYY-MM-DD)") from None


def resolve_backfill_period(date_range="28d", start_date=None, end_date=None, *, today=None):
    normalized = str(date_range or "28d").strip().lower()
    if normalized not in {*BACKFILL_RANGES, "custom"}:
        raise BackfillValidationError("date_range must be one of 7d, 28d, 90d, custom")
    if normalized == "custom":
        if not start_date or not end_date:
            raise BackfillValidationError("custom date_range requires start_date and end_date")
        start = _parse_date(start_date, "start_date")
        end = _parse_date(end_date, "end_date")
    else:
        end = _parse_date(end_date, "end_date") if end_date else (today or date.today()) - timedelta(days=1)
        start = end - timedelta(days=BACKFILL_RANGES[normalized] - 1)
        if start_date and _parse_date(start_date, "start_date") != start:
            raise BackfillValidationError(f"start_date does not match date_range={normalized}")
    days = (end - start).days + 1
    if days < 1:
        raise BackfillValidationError("start_date must be on or before end_date")
    if days > MAX_BACKFILL_DAYS:
        raise BackfillValidationError(f"backfill period cannot exceed {MAX_BACKFILL_DAYS} days")
    return {"date_range": normalized, "start_date": start.isoformat(), "end_date": end.isoformat(), "days": days}


def _dates(period):
    cursor = date.fromisoformat(period["start_date"])
    end = date.fromisoformat(period["end_date"])
    values = []
    while cursor <= end:
        values.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return values


def _account_platform(account_id, platform=None):
    account = get_account(account_id)
    if not account:
        raise BackfillValidationError(f"account {account_id} was not found")
    normalized = str(platform or account.get("platform") or "").strip().lower()
    if not normalized:
        raise BackfillValidationError("platform is required")
    if platform and normalized != str(account.get("platform") or "").strip().lower():
        raise BackfillValidationError("platform does not match the account")
    return account, normalized


def plan_backfill(account_id, *, platform=None, date_range="28d", start_date=None, end_date=None, today=None):
    account, normalized = _account_platform(account_id, platform)
    registration = get_analytics_adapter_registration(normalized)
    reporting_timezone = registration.reporting_timezone if registration else "UTC"
    provider_today = datetime.now(timezone.utc).astimezone(
        ZoneInfo(reporting_timezone)
    ).date()
    period = resolve_backfill_period(
        date_range,
        start_date,
        end_date,
        today=today or provider_today,
    )
    requested_dates = _dates(period)
    metrics = get_account_metrics(account_id, platform=normalized)
    videos = {}
    existing_by_video = {}
    for metric in metrics:
        video_id = metric.get("video_id")
        if not video_id:
            continue
        key = (str(video_id), str(metric.get("content_id") or video_id))
        videos[key] = {"video_id": key[0], "content_id": key[1]}
        if metric.get("period_start") == metric.get("period_end") and metric.get("period_start") in requested_dates:
            existing_by_video.setdefault(key, set()).add(metric["period_start"])
    work = []
    eligible = []
    for key in sorted(videos):
        existing = sorted(existing_by_video.get(key, set()))
        missing = [day for day in requested_dates if day not in existing_by_video.get(key, set())]
        eligible.append({**videos[key], "existing_dates": existing, "missing_dates": missing})
        work.extend({**videos[key], "date": day} for day in missing)
    return {
        "account_id": account_id,
        "platform": normalized,
        "account_status": account.get("status"),
        "period": period,
        "reporting_timezone": reporting_timezone,
        "reporting_date_semantics": "provider reporting calendar date; YouTube interprets each date as midnight-to-midnight Pacific time",
        "eligible_videos": eligible,
        "existing_dates": sorted({day for days in existing_by_video.values() for day in days}),
        "missing_dates": sorted({item["date"] for item in work}),
        "estimated_request_count": len(work),
        "request_cap": MAX_BACKFILL_REQUESTS,
        "work": work,
    }


def get_backfill_status(account_id, *, platform=None):
    _, normalized = _account_platform(account_id, platform)
    state = get_sync_state(account_id, normalized)
    return {"account_id": account_id, "platform": normalized, "state": {key: value for key, value in state.items() if key.startswith("backfill_")}}


def run_backfill(
    account_id, *, platform=None, date_range="28d", start_date=None,
    end_date=None, max_requests=DEFAULT_MAX_REQUESTS, collector=None, now=None,
):
    current = _utc_datetime(now)
    plan = plan_backfill(account_id, platform=platform, date_range=date_range, start_date=start_date, end_date=end_date)
    if str(plan["account_status"] or "").lower() != "connected":
        raise BackfillValidationError("backfill requires a connected account")
    state = get_sync_state(account_id, plan["platform"])
    retry_at = state.get("backfill_next_retry_at")
    if retry_at and _utc_datetime(retry_at) > current:
        raise BackfillRetryNotDue(f"backfill retry is not due until {retry_at}")
    limit = int(max_requests)
    if limit < 1 or limit > MAX_BACKFILL_REQUESTS:
        raise BackfillValidationError(f"max_requests must be between 1 and {MAX_BACKFILL_REQUESTS}")
    attempted_at = current.isoformat()
    mark_backfill_started(account_id, plan["platform"], plan["period"]["start_date"], plan["period"]["end_date"], attempted_at=attempted_at)
    active_collector = collector or AnalyticsCollector()
    completed = []
    failures = []
    for item in plan["work"][:limit]:
        try:
            metric = active_collector.collect(
                item["video_id"], plan["platform"], account_id=account_id,
                content_id=item["content_id"], start_date=item["date"], end_date=item["date"],
            )
            if metric.get("period_start") != item["date"] or metric.get("period_end") != item["date"]:
                raise RuntimeError("collector did not persist the requested single reporting-day window")
            completed.append({**item, "metric_id": metric.get("id")})
            mark_backfill_progress(account_id, plan["platform"], item["date"], updated_at=attempted_at)
        except Exception as exc:
            failures.append({**item, "error": str(exc)})
    remaining = max(0, len(plan["work"]) - len(completed) - len(failures))
    if failures:
        status = "partial" if completed else "failed"
        saved_state = mark_backfill_failure(
            account_id, plan["platform"], f"{len(failures)} backfill request(s) failed",
            failed_at=attempted_at, backoff_seconds=BACKOFF_SECONDS, status=status,
        )
    elif remaining:
        status = "partial"
        saved_state = mark_backfill_failure(
            account_id, plan["platform"], f"request cap reached with {remaining} work item(s) remaining",
            failed_at=attempted_at, backoff_seconds=BACKOFF_SECONDS, status=status,
        )
    else:
        status = "success"
        saved_state = mark_backfill_success(account_id, plan["platform"], succeeded_at=attempted_at)
    return {"status": status, "plan": {key: value for key, value in plan.items() if key != "work"}, "attempted": min(len(plan["work"]), limit), "completed": completed, "failures": failures, "remaining": remaining, "state": saved_state}
