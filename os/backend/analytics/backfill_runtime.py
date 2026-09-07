import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from analytics.backfill import plan_backfill, run_backfill
from analytics.errors import sanitize_analytics_error


DB_PATH = Path("os/database/os.db")
ACTIVE_STATUSES = {"queued", "running", "partial", "failed"}
TERMINAL_STATUSES = {"success", "cancelled"}


def _now(value=None):
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()
    return str(value)


def _safe_error(error):
    return sanitize_analytics_error(error)


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_backfill_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                status TEXT NOT NULL,
                requested_start_date TEXT NOT NULL,
                requested_end_date TEXT NOT NULL,
                request_json TEXT NOT NULL,
                total_work INTEGER NOT NULL DEFAULT 0,
                completed_work INTEGER NOT NULL DEFAULT 0,
                failed_work INTEGER NOT NULL DEFAULT 0,
                remaining_work INTEGER NOT NULL DEFAULT 0,
                current_reporting_date TEXT,
                next_retry_at TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                updated_at TEXT NOT NULL,
                finished_at TEXT,
                last_error TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_backfill_operations_active "
            "ON analytics_backfill_operations(account_id, platform, status)"
        )
        conn.commit()


def _serialize(row):
    if not row:
        return None
    data = dict(row)
    data["request"] = json.loads(data.pop("request_json"))
    total = int(data.get("total_work") or 0)
    completed = int(data.get("completed_work") or 0)
    data["operation_id"] = data.pop("id")
    data["progress_percentage"] = round(completed / total * 100, 2) if total else 100.0
    data["single_process_guarantee"] = True
    return data


def get_operation(operation_id):
    _ensure_table()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM analytics_backfill_operations WHERE id=?", (operation_id,)
        ).fetchone()
    return _serialize(row)


def list_operations(account_id=None, platform=None):
    _ensure_table()
    clauses, params = [], []
    if account_id is not None:
        clauses.append("account_id=?")
        params.append(account_id)
    if platform:
        clauses.append("platform=?")
        params.append(str(platform).strip().lower())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM analytics_backfill_operations {where} ORDER BY id DESC",
            tuple(params),
        ).fetchall()
    return [_serialize(row) for row in rows]


def create_operation(account_id, **request):
    plan = plan_backfill(account_id, **request)
    platform = plan["platform"]
    _ensure_table()
    now = _now()
    payload = {
        "platform": platform,
        "date_range": plan["period"]["date_range"],
        "start_date": plan["period"]["start_date"],
        "end_date": plan["period"]["end_date"],
    }
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        active = conn.execute(
            """
            SELECT id FROM analytics_backfill_operations
            WHERE account_id=? AND platform=?
              AND (status IN ('queued','running','partial')
                   OR (status='failed' AND next_retry_at IS NOT NULL))
            LIMIT 1
            """,
            (account_id, platform),
        ).fetchone()
        if active:
            raise ValueError(f"active backfill operation {active['id']} already exists")
        cursor = conn.execute(
            """
            INSERT INTO analytics_backfill_operations
            (account_id, platform, status, requested_start_date,
             requested_end_date, request_json, total_work, remaining_work,
             created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id, platform, plan["period"]["start_date"],
                plan["period"]["end_date"], json.dumps(payload),
                plan["estimated_request_count"], plan["estimated_request_count"],
                now, now,
            ),
        )
        conn.commit()
        operation_id = cursor.lastrowid
    return get_operation(operation_id)


def cancel_operation(operation_id):
    _ensure_table()
    now = _now()
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE analytics_backfill_operations
            SET status='cancelled', finished_at=?, updated_at=?
            WHERE id=? AND status NOT IN ('success','cancelled')
            """,
            (now, now, operation_id),
        )
        conn.commit()
    if not cursor.rowcount and not get_operation(operation_id):
        return None
    return get_operation(operation_id)


def recover_operations():
    _ensure_table()
    now = _now()
    with _connect() as conn:
        conn.execute(
            "UPDATE analytics_backfill_operations SET status='queued', updated_at=? WHERE status='running'",
            (now,),
        )
        conn.commit()


class AnalyticsBackfillWorker:
    def __init__(self, interval_seconds=None, batch_size=10, *, collector=None, clock=None):
        self.interval_seconds = max(2.0, float(interval_seconds or os.getenv("ANALYTICS_BACKFILL_POLL_SECONDS") or 5))
        self.batch_size = max(1, min(int(batch_size), 20))
        self.collector = collector
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self.last_error = None

    def _claim(self):
        _ensure_table()
        now = _now(self.clock())
        with _connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM analytics_backfill_operations
                WHERE status IN ('queued','partial','failed')
                  AND (next_retry_at IS NULL OR next_retry_at<=?)
                ORDER BY id LIMIT 1
                """,
                (now,),
            ).fetchone()
            if not row:
                conn.commit()
                return None
            started_at = row["started_at"] or now
            changed = conn.execute(
                """
                UPDATE analytics_backfill_operations
                SET status='running', started_at=?, updated_at=?
                WHERE id=? AND status=?
                """,
                (started_at, now, row["id"], row["status"]),
            ).rowcount
            conn.commit()
        return get_operation(row["id"]) if changed else None

    def process_once(self):
        if not self._lock.acquire(blocking=False):
            return None
        try:
            operation = self._claim()
            if not operation:
                return None
            request = operation["request"]
            now = _now(self.clock())
            try:
                result = run_backfill(
                    operation["account_id"], collector=self.collector,
                    max_requests=self.batch_size, now=now,
                    backoff_on_cap=False, **request,
                )
                latest = get_operation(operation["operation_id"])
                if latest and latest["status"] == "cancelled":
                    refreshed = plan_backfill(operation["account_id"], **request)
                    completed = max(
                        0,
                        operation["total_work"] - refreshed["estimated_request_count"],
                    )
                    current_date = (
                        result["completed"][-1]["date"]
                        if result["completed"]
                        else operation.get("current_reporting_date")
                    )
                    with _connect() as conn:
                        conn.execute(
                            """
                            UPDATE analytics_backfill_operations
                            SET completed_work=?, failed_work=?, remaining_work=?,
                                current_reporting_date=?, updated_at=? WHERE id=?
                            """,
                            (
                                completed,
                                len(result["failures"]),
                                refreshed["estimated_request_count"],
                                current_date,
                                now,
                                operation["operation_id"],
                            ),
                        )
                        conn.commit()
                    return get_operation(operation["operation_id"])
                refreshed = plan_backfill(operation["account_id"], **request)
                completed = max(0, operation["total_work"] - refreshed["estimated_request_count"])
                failed = len(result["failures"])
                remaining = refreshed["estimated_request_count"]
                if not remaining:
                    status, finished_at, retry_at, retry_count, error = "success", now, None, 0, None
                elif failed:
                    status = "partial" if completed else "failed"
                    state = result["state"]
                    finished_at, retry_at = None, state.get("backfill_next_retry_at")
                    retry_count, error = state.get("backfill_retry_count") or 0, state.get("backfill_error")
                else:
                    status, finished_at, retry_at, retry_count, error = "queued", None, None, operation["retry_count"], None
                current_date = result["completed"][-1]["date"] if result["completed"] else operation.get("current_reporting_date")
                with _connect() as conn:
                    conn.execute(
                        """
                        UPDATE analytics_backfill_operations
                        SET status=?, completed_work=?, failed_work=?, remaining_work=?,
                            current_reporting_date=?, next_retry_at=?, retry_count=?,
                            updated_at=?, finished_at=?, last_error=? WHERE id=?
                        """,
                        (status, completed, failed, remaining, current_date, retry_at,
                         retry_count, now, finished_at, _safe_error(error), operation["operation_id"]),
                    )
                    conn.commit()
            except Exception as exc:
                with _connect() as conn:
                    conn.execute(
                        "UPDATE analytics_backfill_operations SET status='failed', updated_at=?, last_error=? WHERE id=?",
                        (now, _safe_error(exc), operation["operation_id"]),
                    )
                    conn.commit()
            return get_operation(operation["operation_id"])
        finally:
            self._lock.release()

    def _loop(self):
        recover_operations()
        while not self._stop_event.is_set():
            try:
                self.process_once()
            except Exception as exc:
                self.last_error = _safe_error(exc)
            self._stop_event.wait(self.interval_seconds)

    def start(self):
        if self._thread and self._thread.is_alive():
            return self.status()
        if str(os.getenv("OS_DISABLE_ANALYTICS_BACKFILL_WORKER") or "").lower() in {"1", "true", "yes"}:
            return self.status()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="analytics-backfill-worker", daemon=True)
        self._thread.start()
        return self.status()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=min(self.interval_seconds, 2.0))
        return self.status()

    def status(self):
        return {"running": bool(self._thread and self._thread.is_alive()), "batch_size": self.batch_size, "last_error": self.last_error}


analytics_backfill_worker = AnalyticsBackfillWorker()
