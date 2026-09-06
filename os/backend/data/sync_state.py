import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path("os/database/os.db")
SYNC_KINDS = {"content", "analytics"}
SYNC_STATUSES = {"idle", "running", "success", "partial", "failed"}


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_platform_sync_state_account "
            "ON platform_sync_state(account_id, platform)"
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
