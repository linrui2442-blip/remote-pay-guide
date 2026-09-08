import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from data.database_path import database_path


DB_PATH = database_path()
SYNC_KINDS = {"content", "analytics"}
SYNC_STATUSES = {"idle", "running", "success", "partial", "failed"}
RUNTIME_COMPONENT = "account_sync_scheduler"
RUNTIME_OPERATION = "scheduled_account_sync"
TERMINAL_RUN_STATUSES = {"success", "partial", "failed", "lease_expired", "lease_lost"}


def _connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
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
            "scheduler_lease_run_id": "TEXT",
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runtime_operation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                component TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                account_id INTEGER,
                platform TEXT,
                reporting_date TEXT,
                instance_id TEXT,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                last_heartbeat_at TEXT,
                retry_count INTEGER,
                recovery_of_run_id TEXT,
                reason_code TEXT,
                sanitized_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runtime_history_scope_time "
            "ON runtime_operation_history(component, account_id, platform, started_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runtime_history_status "
            "ON runtime_operation_history(status, finished_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runtime_health_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT NOT NULL,
                account_id INTEGER,
                platform TEXT,
                event_type TEXT NOT NULL,
                health_state TEXT NOT NULL,
                previous_health_state TEXT,
                severity TEXT NOT NULL,
                run_id TEXT,
                instance_id TEXT,
                reason_code TEXT,
                sanitized_message TEXT,
                observed_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runtime_health_scope_time "
            "ON runtime_health_events(component, account_id, platform, observed_at DESC)"
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


def sanitize_operational_error(value, *, max_length=500):
    """Bound and redact operational text before durable persistence or API exposure."""
    if value is None:
        return None
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"(?i)(authorization:\s*bearer\s+)[^\s,;]+", r"\1[REDACTED]", text)
    text = re.sub(
        r"(?i)(access[_-]?token|refresh[_-]?token|client[_-]?secret|id[_-]?token)"
        r"(\s*[=:]\s*|%3[dD])([^\s&,;]+)",
        r"\1\2[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)([?&](?:key|api_key|token|access_token|refresh_token|client_secret)=)[^&#\s]+",
        r"\1[REDACTED]",
        text,
    )
    return text[:max(32, int(max_length))]


def _runtime_limits():
    return (
        max(1, int(os.getenv("RUNTIME_HISTORY_RETENTION_DAYS") or 90)),
        max(100, int(os.getenv("RUNTIME_HISTORY_MAX_ROWS") or 5000)),
        max(100, int(os.getenv("RUNTIME_HEALTH_EVENTS_MAX_ROWS") or 3000)),
    )


def _prune_runtime_history(conn, now_iso):
    retention_days, history_cap, event_cap = _runtime_limits()
    conn.execute(
        "DELETE FROM runtime_operation_history WHERE status != 'running' "
        "AND datetime(COALESCE(finished_at, updated_at)) < datetime(?, ?)",
        (now_iso, f"-{retention_days} days"),
    )
    conn.execute(
        "DELETE FROM runtime_operation_history WHERE status != 'running' AND id NOT IN "
        "(SELECT id FROM runtime_operation_history WHERE status != 'running' "
        "ORDER BY COALESCE(finished_at, updated_at) DESC, id DESC LIMIT ?)",
        (history_cap,),
    )
    conn.execute(
        "DELETE FROM runtime_health_events WHERE id NOT IN "
        "(SELECT id FROM runtime_health_events ORDER BY observed_at DESC, id DESC LIMIT ?)",
        (event_cap,),
    )


def _record_health_transition(
    conn, *, event_type, health_state, observed_at, account_id=None, platform=None,
    severity="info", run_id=None, instance_id=None, reason_code=None, message=None,
):
    """Insert only a changed persistent health state while caller holds a write transaction."""
    row = conn.execute(
        """
        SELECT health_state FROM runtime_health_events
        WHERE component=? AND account_id IS ? AND platform IS ?
        ORDER BY observed_at DESC, id DESC LIMIT 1
        """,
        (RUNTIME_COMPONENT, account_id, platform),
    ).fetchone()
    previous = row["health_state"] if row else None
    if previous == health_state:
        return False
    conn.execute(
        """
        INSERT INTO runtime_health_events
        (component, account_id, platform, event_type, health_state,
         previous_health_state, severity, run_id, instance_id, reason_code,
         sanitized_message, observed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (RUNTIME_COMPONENT, account_id, platform, event_type, health_state,
         previous, severity, run_id, instance_id, reason_code,
         sanitize_operational_error(message), observed_at),
    )
    return True


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
    run_id = str(uuid.uuid4())
    instance_id = str(owner_id).replace("-", "")[:12]
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute(
            "SELECT scheduler_lease_run_id, scheduler_lease_owner, scheduler_lease_expires_at "
            "FROM platform_sync_state WHERE account_id=? AND platform=?",
            (account_id, normalized),
        ).fetchone()
        recovery_of = None
        if (
            previous and previous["scheduler_lease_run_id"]
            and previous["scheduler_lease_owner"] and previous["scheduler_lease_expires_at"]
            and datetime.fromisoformat(previous["scheduler_lease_expires_at"]) <= claimed_at
        ):
            recovery_of = previous["scheduler_lease_run_id"]
        cursor = conn.execute(
            """
            UPDATE platform_sync_state
            SET scheduler_status='running', scheduler_last_attempt_at=?,
                scheduler_last_started_at=?,
                scheduler_lease_owner=?, scheduler_lease_daily_date=?,
                scheduler_lease_acquired_at=?, scheduler_lease_expires_at=?,
                scheduler_lease_last_renewed_at=?, scheduler_lease_run_id=?,
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
                run_id,
                claimed_iso,
                account_id,
                normalized,
                str(daily_date),
                claimed_iso,
                claimed_iso,
            ),
        )
        claimed = cursor.rowcount == 1
        if claimed:
            prior_health = conn.execute(
                "SELECT 1 FROM runtime_health_events WHERE component=? "
                "AND account_id IS ? AND platform IS ? LIMIT 1",
                (RUNTIME_COMPONENT, account_id, normalized),
            ).fetchone()
            if prior_health is None:
                _record_health_transition(
                    conn, event_type="scheduler_ready", health_state="healthy",
                    observed_at=claimed_iso, account_id=account_id,
                    platform=normalized, instance_id=instance_id,
                    reason_code="initial_observation",
                )
            if recovery_of:
                expired_cursor = conn.execute(
                    """
                    UPDATE runtime_operation_history
                    SET status='lease_expired', finished_at=?,
                        duration_seconds=MAX(0, (julianday(?) - julianday(started_at)) * 86400),
                        reason_code='lease_expired_reclaimed', updated_at=?
                    WHERE run_id=? AND status='running'
                    """,
                    (claimed_iso, claimed_iso, claimed_iso, recovery_of),
                )
                if expired_cursor.rowcount != 1:
                    raise RuntimeError("expired scheduler run history is missing")
                _record_health_transition(
                    conn, event_type="lease_expired", health_state="degraded",
                    observed_at=claimed_iso, account_id=account_id, platform=normalized,
                    severity="warning", run_id=recovery_of, instance_id=instance_id,
                    reason_code="lease_expired_reclaimed",
                )
            retry_row = conn.execute(
                "SELECT scheduler_retry_count FROM platform_sync_state "
                "WHERE account_id=? AND platform=?", (account_id, normalized),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO runtime_operation_history
                (run_id, component, operation_type, account_id, platform,
                 reporting_date, instance_id, status, started_at,
                 last_heartbeat_at, retry_count, recovery_of_run_id, reason_code,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, RUNTIME_COMPONENT, RUNTIME_OPERATION, account_id, normalized,
                 str(daily_date), instance_id, claimed_iso, claimed_iso,
                 int(retry_row["scheduler_retry_count"] or 0), recovery_of,
                 "lease_reclaimed" if recovery_of else "scheduled_due",
                 claimed_iso, claimed_iso),
            )
            _record_health_transition(
                conn, event_type="lease_reclaimed" if recovery_of else "run_started",
                health_state="running", observed_at=claimed_iso, account_id=account_id,
                platform=normalized, run_id=run_id, instance_id=instance_id,
                reason_code="lease_reclaimed" if recovery_of else "scheduled_due",
            )
        conn.commit()
    return {
        "claimed": claimed,
        "reason": "claimed" if claimed else "not_claimed",
        "run_id": run_id if claimed else None,
        "recovery_of_run_id": recovery_of if claimed else None,
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
        conn.execute("BEGIN IMMEDIATE")
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
        if cursor.rowcount == 1:
            state = conn.execute(
                "SELECT scheduler_lease_run_id FROM platform_sync_state "
                "WHERE account_id=? AND platform=?", (account_id, normalized),
            ).fetchone()
            history_cursor = conn.execute(
                "UPDATE runtime_operation_history SET last_heartbeat_at=?, updated_at=? "
                "WHERE run_id=? AND status='running' AND account_id=? AND platform=? "
                "AND instance_id=?",
                (renewed_iso, renewed_iso, state["scheduler_lease_run_id"], account_id,
                 normalized, str(owner_id).replace("-", "")[:12]),
            )
            if history_cursor.rowcount != 1:
                raise RuntimeError("active scheduler run history is missing")
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
        conn.execute("BEGIN IMMEDIATE")
        lease = conn.execute(
            "SELECT scheduler_lease_run_id FROM platform_sync_state "
            "WHERE account_id=? AND platform=? AND scheduler_lease_owner=?",
            (account_id, normalized_platform, str(owner_id)),
        ).fetchone()
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
                scheduler_lease_last_renewed_at=NULL, scheduler_lease_run_id=NULL,
                updated_at=?
            WHERE account_id=? AND platform=?
            """ + owner_clause,
            tuple([succeeded_at, str(daily_date), succeeded_at, duration_seconds,
                   succeeded_at, account_id, normalized_platform, str(owner_id)]),
        )
        if cursor.rowcount == 1 and lease and lease["scheduler_lease_run_id"]:
            run_id = lease["scheduler_lease_run_id"]
            history_cursor = conn.execute(
                "UPDATE runtime_operation_history SET status='success', finished_at=?, "
                "duration_seconds=?, reason_code='completed', updated_at=? "
                "WHERE run_id=? AND status='running'",
                (succeeded_at, duration_seconds, succeeded_at, run_id),
            )
            if history_cursor.rowcount != 1:
                raise RuntimeError("active scheduler run history is missing")
            _record_health_transition(
                conn, event_type="run_succeeded", health_state="healthy",
                observed_at=succeeded_at, account_id=account_id,
                platform=normalized_platform, run_id=run_id,
                instance_id=str(owner_id).replace("-", "")[:12], reason_code="completed",
            )
            _prune_runtime_history(conn, succeeded_at)
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
    sanitized_error = sanitize_operational_error(error)
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lease = conn.execute(
            "SELECT scheduler_lease_run_id FROM platform_sync_state "
            "WHERE account_id=? AND platform=? AND scheduler_lease_owner=?",
            (account_id, normalized_platform, str(owner_id)),
        ).fetchone()
        owner_clause = " AND scheduler_lease_owner=?"
        cursor = conn.execute(
            """
            UPDATE platform_sync_state
            SET scheduler_status=?, scheduler_next_retry_at=?, scheduler_retry_count=?,
                last_error=?, last_error_at=?,
                scheduler_last_finished_at=?, scheduler_last_duration_seconds=?,
                scheduler_lease_owner=NULL, scheduler_lease_daily_date=NULL,
                scheduler_lease_acquired_at=NULL, scheduler_lease_expires_at=NULL,
                scheduler_lease_last_renewed_at=NULL, scheduler_lease_run_id=NULL,
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
        if cursor.rowcount == 1 and lease and lease["scheduler_lease_run_id"]:
            run_id = lease["scheduler_lease_run_id"]
            final_status = "partial" if status == "partial" else "failed"
            history_cursor = conn.execute(
                "UPDATE runtime_operation_history SET status=?, finished_at=?, "
                "duration_seconds=?, retry_count=?, reason_code=?, sanitized_error=?, updated_at=? "
                "WHERE run_id=? AND status='running'",
                (final_status, failed_iso, duration_seconds, retry_count,
                 "partial_result" if final_status == "partial" else "execution_failed",
                 sanitized_error, failed_iso, run_id),
            )
            if history_cursor.rowcount != 1:
                raise RuntimeError("active scheduler run history is missing")
            _record_health_transition(
                conn, event_type="retry_scheduled", health_state="retrying",
                observed_at=failed_iso, account_id=account_id,
                platform=normalized_platform, severity="warning", run_id=run_id,
                instance_id=str(owner_id).replace("-", "")[:12],
                reason_code="partial_result" if final_status == "partial" else "execution_failed",
                message=sanitized_error,
            )
            _prune_runtime_history(conn, failed_iso)
        conn.commit()
    final_state = get_sync_state(account_id, normalized_platform, create=False)
    return {
        "applied": cursor.rowcount == 1,
        "reason": "released" if cursor.rowcount == 1 else "lease_lost",
        "sync_state": final_state,
    }


def list_runtime_operation_history(
    *, limit=20, account_id=None, platform=None, status=None,
):
    _ensure_table()
    bounded_limit = min(200, max(1, int(limit)))
    clauses = ["component=?"]
    params = [RUNTIME_COMPONENT]
    if account_id is not None:
        clauses.append("account_id=?")
        params.append(int(account_id))
    if platform:
        clauses.append("platform=?")
        params.append(_normalize_platform(platform))
    if status:
        normalized_status = str(status).strip().lower()
        if normalized_status not in TERMINAL_RUN_STATUSES | {"running"}:
            raise ValueError(f"unsupported runtime status: {status}")
        clauses.append("status=?")
        params.append(normalized_status)
    params.append(bounded_limit)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runtime_operation_history WHERE " + " AND ".join(clauses)
            + " ORDER BY started_at DESC, id DESC LIMIT ?", tuple(params),
        ).fetchall()
    return [_serialize(row) for row in rows]


def list_runtime_health_events(
    *, limit=20, account_id=None, platform=None, severity=None, event_type=None,
):
    _ensure_table()
    bounded_limit = min(200, max(1, int(limit)))
    clauses = ["component=?"]
    params = [RUNTIME_COMPONENT]
    if account_id is not None:
        clauses.append("account_id=?")
        params.append(int(account_id))
    if platform:
        clauses.append("platform=?")
        params.append(_normalize_platform(platform))
    if severity:
        clauses.append("severity=?")
        params.append(str(severity).strip().lower())
    if event_type:
        clauses.append("event_type=?")
        params.append(str(event_type).strip().lower())
    params.append(bounded_limit)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runtime_health_events WHERE " + " AND ".join(clauses)
            + " ORDER BY observed_at DESC, id DESC LIMIT ?", tuple(params),
        ).fetchall()
    return [_serialize(row) for row in rows]


def record_scheduler_lifecycle_event(event_type, health_state, *, instance_id, severity="info"):
    _ensure_table()
    observed_at = _now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        inserted = _record_health_transition(
            conn, event_type=event_type, health_state=health_state,
            observed_at=observed_at, instance_id=str(instance_id)[:12], severity=severity,
        )
        conn.commit()
    return inserted


def record_scheduler_health_transition(
    event_type, health_state, *, account_id, platform, run_id=None,
    instance_id=None, severity="info", reason_code=None, message=None,
):
    _ensure_table()
    observed_at = _now()
    normalized = _normalize_platform(platform)
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        inserted = _record_health_transition(
            conn, event_type=event_type, health_state=health_state,
            observed_at=observed_at, account_id=account_id, platform=normalized,
            run_id=run_id, instance_id=str(instance_id or "")[:12] or None,
            severity=severity, reason_code=reason_code, message=message,
        )
        conn.commit()
    return inserted


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
