import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


DB_PATH = Path("os/database/os.db")
SYNC_KINDS = {"content", "analytics"}
SYNC_STATUSES = {"idle", "running", "success", "partial", "failed"}


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat()


def _normalize_platform(platform):
    normalized = str(platform or "").strip().lower()
    if not normalized:
        raise ValueError("platform is required")
    return normalized


def _ensure_table():
    with _connect() as conn:
        # Serialize lazy schema inspection/migration across backend processes.
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS platform_sync_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                content_cursor TEXT,
                analytics_cursor TEXT,
                content_status TEXT NOT NULL DEFAULT 'idle',
                analytics_status TEXT NOT NULL DEFAULT 'idle',
                last_content_sync_at TEXT,
                last_analytics_sync_at TEXT,
                last_success_at TEXT,
                last_error TEXT,
                last_error_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(account_id, platform)
            )
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(platform_sync_state)").fetchall()
        }
        scheduler_columns = {
            "scheduler_status": "TEXT NOT NULL DEFAULT 'idle'",
            "scheduler_last_attempt_at": "TEXT",
            "scheduler_last_success_at": "TEXT",
            "scheduler_last_daily_date": "TEXT",
            "scheduler_next_retry_at": "TEXT",
            "scheduler_retry_count": "INTEGER NOT NULL DEFAULT 0",
            "scheduler_lease_owner": "TEXT",
            "scheduler_lease_daily_date": "TEXT",
            "scheduler_lease_acquired_at": "TEXT",
            "scheduler_lease_expires_at": "TEXT",
            "scheduler_lease_last_renewed_at": "TEXT",
            "scheduler_last_started_at": "TEXT",
            "scheduler_last_finished_at": "TEXT",
            "scheduler_last_duration_seconds": "REAL",
            "backfill_status": "TEXT NOT NULL DEFAULT 'idle'",
            "backfill_start_date": "TEXT",
            "backfill_end_date": "TEXT",
            "backfill_last_completed_date": "TEXT",
            "backfill_last_attempt_at": "TEXT",
            "backfill_last_success_at": "TEXT",
            "backfill_next_retry_at": "TEXT",
            "backfill_retry_count": "INTEGER NOT NULL DEFAULT 0",
            "backfill_error": "TEXT",
            "backfill_no_data_coverage": "TEXT",
        }
        for name, field_type in scheduler_columns.items():
            if name not in columns:
                conn.execute(
                    f"ALTER TABLE platform_sync_state ADD COLUMN {name} {field_type}"
                )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_platform_sync_state_account "
            "ON platform_sync_state(account_id, platform)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_platform_sync_state_scheduler_lease "
            "ON platform_sync_state(scheduler_lease_expires_at)"
        )
        conn.commit()


def _serialize(row):
    return dict(row) if row else None


def ensure_sync_state(account_id, platform):
    _ensure_table()
    normalized_platform = _normalize_platform(platform)
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO platform_sync_state
            (account_id, platform, content_status, analytics_status,
             created_at, updated_at)
            VALUES (?, ?, 'idle', 'idle', ?, ?)
            """,
            (account_id, normalized_platform, now, now),
        )
        conn.commit()
    return get_sync_state(account_id, normalized_platform, create=False)


def get_sync_state(account_id, platform, *, create=True):
    _ensure_table()
    normalized_platform = _normalize_platform(platform)
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM platform_sync_state WHERE account_id=? AND platform=?",
            (account_id, normalized_platform),
        ).fetchone()
    if row is None and create:
        return ensure_sync_state(account_id, normalized_platform)
    return _serialize(row)


def get_backfill_no_data_coverage(account_id, platform):
    state = get_sync_state(account_id, platform)
    try:
        value = json.loads(state.get("backfill_no_data_coverage") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def record_backfill_no_data(
    account_id, platform, video_id, content_id, reporting_date, *, observed_at=None
):
    normalized = _normalize_platform(platform)
    coverage = get_backfill_no_data_coverage(account_id, normalized)
    key = f"{video_id}\u001f{content_id}"
    observations = coverage.setdefault(key, {})
    observations[str(reporting_date)] = observed_at or _now()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()
    coverage = {
        item_key: {
            day: timestamp for day, timestamp in item_dates.items() if day >= cutoff
        }
        for item_key, item_dates in coverage.items()
        if isinstance(item_dates, dict)
    }
    coverage = {key: dates for key, dates in coverage.items() if dates}
    with _connect() as conn:
        conn.execute(
            "UPDATE platform_sync_state SET backfill_no_data_coverage=?, updated_at=? "
            "WHERE account_id=? AND platform=?",
            (json.dumps(coverage, sort_keys=True), observed_at or _now(), account_id, normalized),
        )
        conn.commit()
    return coverage


def list_sync_states(account_id=None, platform=None):
    _ensure_table()
    clauses = []
    params = []
    if account_id is not None:
        clauses.append("account_id=?")
        params.append(account_id)
    if platform:
        clauses.append("platform=?")
        params.append(_normalize_platform(platform))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM platform_sync_state {where} ORDER BY account_id, platform",
            tuple(params),
        ).fetchall()
    return [_serialize(row) for row in rows]


def _validate_kind(kind):
    normalized = str(kind or "").strip().lower()
    if normalized not in SYNC_KINDS:
        raise ValueError(f"unsupported sync kind: {kind}")
    return normalized


def mark_sync_started(account_id, platform, kind):
    normalized_platform = _normalize_platform(platform)
    normalized_kind = _validate_kind(kind)
    ensure_sync_state(account_id, normalized_platform)
    now = _now()
    status_column = f"{normalized_kind}_status"
    with _connect() as conn:
        conn.execute(
            f"UPDATE platform_sync_state SET {status_column}='running', updated_at=? "
            "WHERE account_id=? AND platform=?",
            (now, account_id, normalized_platform),
        )
        conn.commit()
    return get_sync_state(account_id, normalized_platform, create=False)


def mark_sync_success(account_id, platform, kind, *, cursor=None):
    normalized_platform = _normalize_platform(platform)
    normalized_kind = _validate_kind(kind)
    ensure_sync_state(account_id, normalized_platform)
    now = _now()
    status_column = f"{normalized_kind}_status"
    cursor_column = f"{normalized_kind}_cursor"
    sync_at_column = f"last_{normalized_kind}_sync_at"
    with _connect() as conn:
        if cursor is None:
            conn.execute(
                f"""
                UPDATE platform_sync_state
                SET {status_column}='success', {sync_at_column}=?,
                    last_success_at=?, last_error=NULL, last_error_at=NULL,
                    updated_at=?
                WHERE account_id=? AND platform=?
                """,
                (now, now, now, account_id, normalized_platform),
            )
        else:
            conn.execute(
                f"""
                UPDATE platform_sync_state
                SET {status_column}='success', {cursor_column}=?,
                    {sync_at_column}=?, last_success_at=?, last_error=NULL,
                    last_error_at=NULL, updated_at=?
                WHERE account_id=? AND platform=?
                """,
                (str(cursor), now, now, now, account_id, normalized_platform),
            )
        conn.commit()
    return get_sync_state(account_id, normalized_platform, create=False)


def mark_sync_partial(account_id, platform, kind, *, cursor=None, error=None):
    normalized_platform = _normalize_platform(platform)
    normalized_kind = _validate_kind(kind)
    ensure_sync_state(account_id, normalized_platform)
    now = _now()
    status_column = f"{normalized_kind}_status"
    cursor_column = f"{normalized_kind}_cursor"
    sync_at_column = f"last_{normalized_kind}_sync_at"
    with _connect() as conn:
        if cursor is None:
            conn.execute(
                f"""
                UPDATE platform_sync_state
                SET {status_column}='partial', {sync_at_column}=?,
                    last_success_at=?, last_error=?, last_error_at=?, updated_at=?
                WHERE account_id=? AND platform=?
                """,
                (now, now, str(error or "partial sync"), now, now, account_id, normalized_platform),
            )
        else:
            conn.execute(
                f"""
                UPDATE platform_sync_state
                SET {status_column}='partial', {cursor_column}=?,
                    {sync_at_column}=?, last_success_at=?, last_error=?,
                    last_error_at=?, updated_at=?
                WHERE account_id=? AND platform=?
                """,
                (str(cursor), now, now, str(error or "partial sync"), now, now, account_id, normalized_platform),
            )
        conn.commit()
    return get_sync_state(account_id, normalized_platform, create=False)


def mark_sync_failure(account_id, platform, kind, error):
    normalized_platform = _normalize_platform(platform)
    normalized_kind = _validate_kind(kind)
    ensure_sync_state(account_id, normalized_platform)
    now = _now()
    status_column = f"{normalized_kind}_status"
    with _connect() as conn:
        conn.execute(
            f"""
            UPDATE platform_sync_state
            SET {status_column}='failed', last_error=?, last_error_at=?, updated_at=?
            WHERE account_id=? AND platform=?
            """,
            (str(error), now, now, account_id, normalized_platform),
        )
        conn.commit()
    return get_sync_state(account_id, normalized_platform, create=False)


def mark_scheduler_attempt(account_id, platform, *, attempted_at=None):
    normalized_platform = _normalize_platform(platform)
    ensure_sync_state(account_id, normalized_platform)
    attempted_at = attempted_at or _now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE platform_sync_state
            SET scheduler_status='running', scheduler_last_attempt_at=?, updated_at=?
            WHERE account_id=? AND platform=?
            """,
            (attempted_at, attempted_at, account_id, normalized_platform),
        )
        conn.commit()
    return get_sync_state(account_id, normalized_platform, create=False)


def try_claim_scheduler_run(
    account_id,
    platform,
    daily_date,
    owner_id,
    *,
    now=None,
    lease_seconds=1800,
):
    """Atomically claim one account/reporting-day run in the shared SQLite DB."""
    normalized = _normalize_platform(platform)
    if not str(owner_id or "").strip():
        raise ValueError("owner_id is required")
    ensure_sync_state(account_id, normalized)
    claimed_at = datetime.fromisoformat(now) if isinstance(now, str) else now
    claimed_at = claimed_at or datetime.now(timezone.utc)
    if claimed_at.tzinfo is None:
        claimed_at = claimed_at.replace(tzinfo=timezone.utc)
    claimed_at = claimed_at.astimezone(timezone.utc)
    claimed_iso = claimed_at.isoformat()
    expires_iso = (claimed_at + timedelta(seconds=max(1, int(lease_seconds)))).isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE platform_sync_state
            SET scheduler_status='running', scheduler_last_attempt_at=?,
                scheduler_last_started_at=?,
                scheduler_lease_owner=?, scheduler_lease_daily_date=?,
                scheduler_lease_acquired_at=?, scheduler_lease_expires_at=?,
                scheduler_lease_last_renewed_at=?,
                updated_at=?
            WHERE account_id=? AND platform=?
              AND (scheduler_last_daily_date IS NULL OR scheduler_last_daily_date != ?)
              AND (scheduler_next_retry_at IS NULL
                   OR datetime(scheduler_next_retry_at) <= datetime(?))
              AND (scheduler_lease_owner IS NULL
                   OR scheduler_lease_expires_at IS NULL
                   OR datetime(scheduler_lease_expires_at) <= datetime(?))
            """,
            (
                claimed_iso,
                claimed_iso,
                str(owner_id),
                str(daily_date),
                claimed_iso,
                expires_iso,
                claimed_iso,
                claimed_iso,
                account_id,
                normalized,
                str(daily_date),
                claimed_iso,
                claimed_iso,
            ),
        )
        conn.commit()
        claimed = cursor.rowcount == 1
    return {
        "claimed": claimed,
        "reason": "claimed" if claimed else "not_claimed",
        "sync_state": get_sync_state(account_id, normalized, create=False),
    }


def renew_scheduler_lease(
    account_id,
    platform,
    daily_date,
    owner_id,
    *,
    renewed_at=None,
    lease_seconds=1800,
):
    """Extend a live lease only while the same owner still holds it."""
    normalized = _normalize_platform(platform)
    renewed = datetime.fromisoformat(renewed_at) if isinstance(renewed_at, str) else renewed_at
    renewed = renewed or datetime.now(timezone.utc)
    if renewed.tzinfo is None:
        renewed = renewed.replace(tzinfo=timezone.utc)
    renewed = renewed.astimezone(timezone.utc)
    renewed_iso = renewed.isoformat()
    expires_iso = (renewed + timedelta(seconds=max(1, int(lease_seconds)))).isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE platform_sync_state
            SET scheduler_lease_expires_at=?, scheduler_lease_last_renewed_at=?,
                updated_at=?
            WHERE account_id=? AND platform=?
              AND scheduler_lease_owner=?
              AND scheduler_lease_daily_date=?
              AND scheduler_lease_expires_at IS NOT NULL
              AND datetime(scheduler_lease_expires_at) > datetime(?)
              AND (scheduler_last_daily_date IS NULL OR scheduler_last_daily_date != ?)
            """,
            (
                expires_iso, renewed_iso, renewed_iso, account_id, normalized,
                str(owner_id), str(daily_date), renewed_iso, str(daily_date),
            ),
        )
        conn.commit()
    return {
        "applied": cursor.rowcount == 1,
        "reason": "renewed" if cursor.rowcount == 1 else "lease_lost",
        "sync_state": get_sync_state(account_id, normalized, create=False),
    }


def mark_scheduler_success(
    account_id, platform, daily_date, *, owner_id, succeeded_at=None,
    duration_seconds=None,
):
    normalized_platform = _normalize_platform(platform)
    ensure_sync_state(account_id, normalized_platform)
    succeeded_at = succeeded_at or _now()
    with _connect() as conn:
        owner_clause = " AND scheduler_lease_owner=?"
        cursor = conn.execute(
            """
            UPDATE platform_sync_state
            SET scheduler_status='success', scheduler_last_success_at=?,
                scheduler_last_daily_date=?, scheduler_next_retry_at=NULL,
                scheduler_retry_count=0, last_error=NULL, last_error_at=NULL,
                scheduler_last_finished_at=?, scheduler_last_duration_seconds=?,
                scheduler_lease_owner=NULL, scheduler_lease_daily_date=NULL,
                scheduler_lease_acquired_at=NULL, scheduler_lease_expires_at=NULL,
                scheduler_lease_last_renewed_at=NULL,
                updated_at=?
            WHERE account_id=? AND platform=?
            """ + owner_clause,
            tuple([succeeded_at, str(daily_date), succeeded_at, duration_seconds,
                   succeeded_at, account_id, normalized_platform, str(owner_id)]),
        )
        conn.commit()
    state = get_sync_state(account_id, normalized_platform, create=False)
    return {
        "applied": cursor.rowcount == 1,
        "reason": "released" if cursor.rowcount == 1 else "lease_lost",
        "sync_state": state,
    }


def mark_scheduler_failure(
    account_id,
    platform,
    error,
    *,
    failed_at=None,
    backoff_seconds=(300, 900, 3600),
    status="failed",
    owner_id,
    duration_seconds=None,
):
    normalized_platform = _normalize_platform(platform)
    state = ensure_sync_state(account_id, normalized_platform)
    failed = (
        datetime.fromisoformat(failed_at)
        if failed_at
        else datetime.now(timezone.utc)
    )
    if failed.tzinfo is None:
        failed = failed.replace(tzinfo=timezone.utc)
    retry_count = int(state.get("scheduler_retry_count") or 0) + 1
    delays = tuple(int(value) for value in backoff_seconds) or (3600,)
    delay = delays[min(retry_count - 1, len(delays) - 1)]
    next_retry = failed + timedelta(seconds=delay)
    failed_iso = failed.isoformat()
    with _connect() as conn:
        owner_clause = " AND scheduler_lease_owner=?"
        cursor = conn.execute(
            """
            UPDATE platform_sync_state
            SET scheduler_status=?, scheduler_next_retry_at=?, scheduler_retry_count=?,
                last_error=?, last_error_at=?,
                scheduler_last_finished_at=?, scheduler_last_duration_seconds=?,
                scheduler_lease_owner=NULL, scheduler_lease_daily_date=NULL,
                scheduler_lease_acquired_at=NULL, scheduler_lease_expires_at=NULL,
                scheduler_lease_last_renewed_at=NULL,
                updated_at=?
            WHERE account_id=? AND platform=?
            """ + owner_clause,
            tuple([
                "partial" if status == "partial" else "failed",
                next_retry.isoformat(), retry_count, str(error), failed_iso,
                failed_iso, duration_seconds, failed_iso, account_id,
                normalized_platform, str(owner_id),
            ]),
        )
        conn.commit()
    final_state = get_sync_state(account_id, normalized_platform, create=False)
    return {
        "applied": cursor.rowcount == 1,
        "reason": "released" if cursor.rowcount == 1 else "lease_lost",
        "sync_state": final_state,
    }


def get_scheduler_persistent_summary(*, now=None, stuck_warning_seconds=3600):
    """Return provider-neutral scheduler health counters without secret data."""
    _ensure_table()
    current = datetime.fromisoformat(now) if isinstance(now, str) else now
    current = current or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current_iso = current.astimezone(timezone.utc).isoformat()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN scheduler_lease_owner IS NOT NULL
                          AND scheduler_lease_expires_at IS NOT NULL
                          AND datetime(scheduler_lease_expires_at) > datetime(?)
                         THEN 1 ELSE 0 END) AS active_leases,
                SUM(CASE WHEN scheduler_lease_owner IS NOT NULL
                          AND scheduler_lease_expires_at IS NOT NULL
                          AND datetime(scheduler_lease_expires_at) <= datetime(?)
                         THEN 1 ELSE 0 END) AS expired_leases,
                SUM(CASE WHEN scheduler_next_retry_at IS NOT NULL
                          AND datetime(scheduler_next_retry_at) > datetime(?)
                         THEN 1 ELSE 0 END) AS accounts_in_retry,
                MAX(scheduler_last_success_at) AS last_success_at,
                MAX(CASE WHEN scheduler_status IN ('failed', 'partial')
                         THEN last_error_at END) AS last_failure_at,
                MAX(scheduler_last_started_at) AS last_started_at,
                MAX(scheduler_last_finished_at) AS last_finished_at,
                (SELECT scheduler_last_duration_seconds FROM platform_sync_state
                 WHERE scheduler_last_finished_at IS NOT NULL
                 ORDER BY scheduler_last_finished_at DESC LIMIT 1) AS last_duration_seconds,
                MIN(CASE WHEN scheduler_lease_owner IS NOT NULL
                         AND datetime(scheduler_lease_expires_at) > datetime(?)
                         THEN scheduler_lease_acquired_at END) AS run_started_at,
                MAX(CASE WHEN scheduler_lease_owner IS NOT NULL
                         AND datetime(scheduler_lease_expires_at) > datetime(?)
                         THEN scheduler_lease_expires_at END) AS lease_expires_at,
                MAX(CASE WHEN scheduler_lease_owner IS NOT NULL
                         AND datetime(scheduler_lease_expires_at) > datetime(?)
                         THEN scheduler_lease_last_renewed_at END) AS last_lease_renewed_at,
                SUM(CASE WHEN scheduler_lease_owner IS NOT NULL
                          AND datetime(scheduler_lease_expires_at) > datetime(?)
                          AND (julianday(?) - julianday(scheduler_lease_acquired_at)) * 86400 > ?
                         THEN 1 ELSE 0 END) AS stuck_accounts_count
            FROM platform_sync_state
            """,
            (current_iso, current_iso, current_iso, current_iso, current_iso,
             current_iso, current_iso, current_iso, int(stuck_warning_seconds)),
        ).fetchone()
    result = _serialize(row) or {}
    for key in ("active_leases", "expired_leases", "accounts_in_retry", "stuck_accounts_count"):
        result[key] = int(result.get(key) or 0)
    started = result.get("run_started_at")
    expires = result.get("lease_expires_at")
    result["current_run_age_seconds"] = max(
        0.0, (current - datetime.fromisoformat(started)).total_seconds()
    ) if started else None
    result["lease_remaining_seconds"] = max(
        0.0, (datetime.fromisoformat(expires) - current).total_seconds()
    ) if expires else None
    return result


def mark_backfill_started(account_id, platform, start_date, end_date, *, attempted_at=None):
    normalized = _normalize_platform(platform)
    ensure_sync_state(account_id, normalized)
    attempted_at = attempted_at or _now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE platform_sync_state
            SET backfill_status='running', backfill_start_date=?,
                backfill_end_date=?, backfill_last_attempt_at=?, updated_at=?
            WHERE account_id=? AND platform=?
            """,
            (start_date, end_date, attempted_at, attempted_at, account_id, normalized),
        )
        conn.commit()
    return get_sync_state(account_id, normalized, create=False)


def mark_backfill_progress(account_id, platform, completed_date, *, updated_at=None):
    normalized = _normalize_platform(platform)
    ensure_sync_state(account_id, normalized)
    updated_at = updated_at or _now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE platform_sync_state SET backfill_last_completed_date=?, updated_at=?
            WHERE account_id=? AND platform=?
            """,
            (completed_date, updated_at, account_id, normalized),
        )
        conn.commit()
    return get_sync_state(account_id, normalized, create=False)


def mark_backfill_success(account_id, platform, *, succeeded_at=None):
    normalized = _normalize_platform(platform)
    ensure_sync_state(account_id, normalized)
    succeeded_at = succeeded_at or _now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE platform_sync_state
            SET backfill_status='success', backfill_last_success_at=?,
                backfill_next_retry_at=NULL, backfill_retry_count=0,
                backfill_error=NULL, updated_at=?
            WHERE account_id=? AND platform=?
            """,
            (succeeded_at, succeeded_at, account_id, normalized),
        )
        conn.commit()
    return get_sync_state(account_id, normalized, create=False)


def mark_backfill_failure(
    account_id, platform, error, *, failed_at=None,
    backoff_seconds=(300, 900, 3600), status="failed",
):
    normalized = _normalize_platform(platform)
    state = ensure_sync_state(account_id, normalized)
    failed = datetime.fromisoformat(failed_at) if failed_at else datetime.now(timezone.utc)
    if failed.tzinfo is None:
        failed = failed.replace(tzinfo=timezone.utc)
    retry_count = int(state.get("backfill_retry_count") or 0) + 1
    delays = tuple(int(value) for value in backoff_seconds) or (3600,)
    retry_at = failed + timedelta(seconds=delays[min(retry_count - 1, len(delays) - 1)])
    failed_at = failed.isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE platform_sync_state
            SET backfill_status=?, backfill_last_attempt_at=?,
                backfill_next_retry_at=?, backfill_retry_count=?,
                backfill_error=?, updated_at=?
            WHERE account_id=? AND platform=?
            """,
            (
                "partial" if status == "partial" else "failed",
                failed_at, retry_at.isoformat(), retry_count, str(error),
                failed_at, account_id, normalized,
            ),
        )
        conn.commit()
    return get_sync_state(account_id, normalized, create=False)
