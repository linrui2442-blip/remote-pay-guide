import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from analytics.manager import get_latest_video_metrics
from assets.manager import get_asset
from data.growth import get_content_funnel
from publish.manager import get_publish_tasks


DB_PATH = Path("os/database/os.db")
DEFAULT_ACTIVE_LIMIT = 10
TRACKING_STATES = {"active", "historical", "archived"}


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS content_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                content_id TEXT NOT NULL,
                platform_video_id TEXT NOT NULL,
                title TEXT,
                published_at TEXT,
                state TEXT NOT NULL DEFAULT 'historical',
                pinned INTEGER NOT NULL DEFAULT 0,
                first_tracked_at TEXT NOT NULL,
                last_active_at TEXT,
                left_active_at TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(account_id, platform, platform_video_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS content_history_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                content_id TEXT NOT NULL,
                platform_video_id TEXT NOT NULL,
                title TEXT,
                published_at TEXT,
                views INTEGER DEFAULT 0,
                watch_time INTEGER DEFAULT 0,
                average_view_duration REAL,
                average_view_percentage REAL,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                referral_clicks INTEGER DEFAULT 0,
                conversions INTEGER DEFAULT 0,
                conversion_value REAL DEFAULT 0,
                summarized_at TEXT NOT NULL,
                UNIQUE(account_id, platform, platform_video_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tracking_account_platform "
            "ON content_tracking(account_id, platform, state)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_account_platform "
            "ON content_history_summary(account_id, platform)"
        )
        conn.commit()


def _normalize_platform(platform):
    return (platform or "").strip().lower()


def _iso_timestamp(value):
    if not value:
        return 0.0
    try:
        normalized = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return 0.0


def _task_metadata(task):
    asset = get_asset(task.get("video_id")) if task.get("video_id") else None
    metadata = (asset or {}).get("metadata") or {}
    published_at = (
        metadata.get("published_at")
        or task.get("scheduled_time")
        or task.get("created_at")
    )
    return {
        "content_id": task.get("video_id") or task.get("asset_id") or task.get("platform_video_id"),
        "platform_video_id": task.get("platform_video_id"),
        "title": task.get("title") or metadata.get("title") or task.get("platform_video_id"),
        "published_at": published_at,
    }


def _eligible_tasks(account_id, platform=None):
    normalized_platform = _normalize_platform(platform) or None
    items = []
    for task in get_publish_tasks():
        if task.get("account_id") != account_id:
            continue
        if (task.get("status") or "").strip().lower() != "published":
            continue
        task_platform = _normalize_platform(task.get("platform"))
        if normalized_platform and task_platform != normalized_platform:
            continue
        if not task.get("platform_video_id"):
            continue
        metadata = _task_metadata(task)
        items.append({**task, "_tracking": metadata})

    items.sort(
        key=lambda task: (
            _iso_timestamp(task["_tracking"].get("published_at")),
            int(task.get("id") or 0),
        ),
        reverse=True,
    )
    return items


def _serialize_tracking(row):
    if not row:
        return None
    data = dict(row)
    data["pinned"] = bool(data.get("pinned"))
    return data


def _latest_metric_for(video_id, platform):
    metrics = get_latest_video_metrics(video_id)
    normalized_platform = _normalize_platform(platform)
    for metric in metrics:
        if _normalize_platform(metric.get("platform")) == normalized_platform:
            return metric
    return metrics[0] if metrics else {}


def _upsert_history_summary(record):
    metric = _latest_metric_for(record["content_id"], record["platform"])
    funnel = get_content_funnel(record["content_id"])
    intent_by_type = funnel.get("intent", {}).get("by_type", {})
    conversion = funnel.get("conversion", {})
    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO content_history_summary
            (account_id, platform, content_id, platform_video_id, title,
             published_at, views, watch_time, average_view_duration,
             average_view_percentage, likes, comments, shares,
             referral_clicks, conversions, conversion_value, summarized_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, platform, platform_video_id) DO UPDATE SET
                content_id=excluded.content_id,
                title=excluded.title,
                published_at=excluded.published_at,
                views=excluded.views,
                watch_time=excluded.watch_time,
                average_view_duration=excluded.average_view_duration,
                average_view_percentage=excluded.average_view_percentage,
                likes=excluded.likes,
                comments=excluded.comments,
                shares=excluded.shares,
                referral_clicks=excluded.referral_clicks,
                conversions=excluded.conversions,
                conversion_value=excluded.conversion_value,
                summarized_at=excluded.summarized_at
            """,
            (
                record["account_id"],
                record["platform"],
                record["content_id"],
                record["platform_video_id"],
                record.get("title"),
                record.get("published_at"),
                int(metric.get("views") or 0),
                int(metric.get("watch_time") or 0),
                metric.get("average_view_duration"),
                metric.get("retention"),
                int(metric.get("likes") or 0),
                int(metric.get("comments") or 0),
                int(metric.get("shares") or 0),
                int(intent_by_type.get("binance_referral_click", 0) or 0),
                int(conversion.get("total", 0) or 0),
                float(conversion.get("value", 0) or 0),
                now,
            ),
        )
        conn.commit()


def refresh_tracking_policy(account_id, platform, active_limit=DEFAULT_ACTIVE_LIMIT):
    """Refresh Active/Historical tracking state for one bound platform account.

    The newest ``active_limit`` published items stay ACTIVE. Manually pinned
    items remain ACTIVE even after they fall outside the newest window. Items
    leaving ACTIVE become HISTORICAL; their latest traffic/conversion outcome
    is summarized without deleting raw historical data.
    """
    _ensure_tables()
    normalized_platform = _normalize_platform(platform)
    if not normalized_platform:
        raise ValueError("platform is required")
    active_limit = max(1, min(int(active_limit or DEFAULT_ACTIVE_LIMIT), 200))
    tasks = _eligible_tasks(account_id, normalized_platform)

    with _connect() as conn:
        existing_rows = conn.execute(
            "SELECT * FROM content_tracking WHERE account_id=? AND platform=?",
            (account_id, normalized_platform),
        ).fetchall()
    existing = {row["platform_video_id"]: dict(row) for row in existing_rows}
    pinned_ids = {
        video_id
        for video_id, row in existing.items()
        if bool(row.get("pinned"))
    }
    newest_ids = {
        task["_tracking"]["platform_video_id"]
        for task in tasks[:active_limit]
    }
    active_ids = newest_ids | pinned_ids
    now = datetime.now(timezone.utc).isoformat()
    transitioned_to_history = []

    with _connect() as conn:
        for task in tasks:
            metadata = task["_tracking"]
            video_id = metadata["platform_video_id"]
            old = existing.get(video_id)
            previous_state = old.get("state") if old else None
            pinned = bool(old.get("pinned")) if old else False
            state = "active" if video_id in active_ids else "historical"
            first_tracked_at = old.get("first_tracked_at") if old else now
            last_active_at = now if state == "active" else (old or {}).get("last_active_at")
            left_active_at = (old or {}).get("left_active_at")
            if previous_state == "active" and state == "historical":
                left_active_at = now

            conn.execute(
                """
                INSERT INTO content_tracking
                (account_id, platform, content_id, platform_video_id, title,
                 published_at, state, pinned, first_tracked_at, last_active_at,
                 left_active_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, platform, platform_video_id) DO UPDATE SET
                    content_id=excluded.content_id,
                    title=excluded.title,
                    published_at=excluded.published_at,
                    state=excluded.state,
                    pinned=excluded.pinned,
                    last_active_at=excluded.last_active_at,
                    left_active_at=excluded.left_active_at,
                    updated_at=excluded.updated_at
                """,
                (
                    account_id,
                    normalized_platform,
                    metadata["content_id"],
                    video_id,
                    metadata.get("title"),
                    metadata.get("published_at"),
                    state,
                    int(pinned),
                    first_tracked_at,
                    last_active_at,
                    left_active_at,
                    now,
                ),
            )

            if state == "historical" and previous_state != "historical":
                transitioned_to_history.append(
                    {
                        "account_id": account_id,
                        "platform": normalized_platform,
                        **metadata,
                    }
                )
        conn.commit()

    for record in transitioned_to_history:
        _upsert_history_summary(record)

    records = get_tracking_records(account_id, normalized_platform)
    return {
        "account_id": account_id,
        "platform": normalized_platform,
        "active_limit": active_limit,
        "active": len([item for item in records if item["state"] == "active"]),
        "historical": len([item for item in records if item["state"] == "historical"]),
        "archived": len([item for item in records if item["state"] == "archived"]),
        "pinned": len([item for item in records if item["pinned"]]),
        "records": records,
    }


def get_tracking_records(account_id, platform=None, state=None):
    _ensure_tables()
    clauses = ["account_id=?"]
    params = [account_id]
    normalized_platform = _normalize_platform(platform)
    if normalized_platform:
        clauses.append("platform=?")
        params.append(normalized_platform)
    if state:
        normalized_state = str(state).strip().lower()
        if normalized_state not in TRACKING_STATES:
            raise ValueError(f"unsupported tracking state: {state}")
        clauses.append("state=?")
        params.append(normalized_state)

    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM content_tracking WHERE {' AND '.join(clauses)} "
            "ORDER BY CASE state WHEN 'active' THEN 0 WHEN 'historical' THEN 1 ELSE 2 END, "
            "published_at DESC, id DESC",
            tuple(params),
        ).fetchall()
    return [_serialize_tracking(row) for row in rows]


def get_active_publish_tasks(account_id, platform, active_limit=DEFAULT_ACTIVE_LIMIT):
    refreshed = refresh_tracking_policy(account_id, platform, active_limit=active_limit)
    active_ids = {
        item["platform_video_id"]
        for item in refreshed["records"]
        if item["state"] == "active"
    }
    return [
        task
        for task in _eligible_tasks(account_id, platform)
        if task.get("platform_video_id") in active_ids
    ]


def set_tracking_pinned(account_id, platform, platform_video_id, pinned=True, active_limit=DEFAULT_ACTIVE_LIMIT):
    _ensure_tables()
    normalized_platform = _normalize_platform(platform)
    refresh_tracking_policy(account_id, normalized_platform, active_limit=active_limit)
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE content_tracking
            SET pinned=?, updated_at=?
            WHERE account_id=? AND platform=? AND platform_video_id=?
            """,
            (
                int(bool(pinned)),
                datetime.now(timezone.utc).isoformat(),
                account_id,
                normalized_platform,
                platform_video_id,
            ),
        )
        conn.commit()
    if cursor.rowcount == 0:
        raise LookupError("tracking item not found")
    return refresh_tracking_policy(account_id, normalized_platform, active_limit=active_limit)


def get_history_summaries(account_id, platform=None):
    _ensure_tables()
    clauses = ["account_id=?"]
    params = [account_id]
    normalized_platform = _normalize_platform(platform)
    if normalized_platform:
        clauses.append("platform=?")
        params.append(normalized_platform)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM content_history_summary WHERE {' AND '.join(clauses)} "
            "ORDER BY published_at DESC, id DESC",
            tuple(params),
        ).fetchall()
    return [dict(row) for row in rows]
