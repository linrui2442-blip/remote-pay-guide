import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from analytics.manager import save_metric
from analytics.models import AnalyticsMetric
from data.query import query_data_center
from data.sync_state import get_sync_state
from integrations.sync_scheduler import BackgroundAccountSyncScheduler, due_accounts


DB_PATH = Path("os/database/os.db")
NOW = datetime(2026, 9, 7, 1, 0, tzinfo=timezone.utc)


def reset_test_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.unlink(missing_ok=True)


def add_account(platform="youtube", status="connected"):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                account_name TEXT,
                status TEXT,
                access_token TEXT,
                refresh_token TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cursor = conn.execute(
            "INSERT INTO accounts (platform, account_name, status) VALUES (?, ?, ?)",
            (platform, f"{platform}-{status}", status),
        )
        conn.commit()
        return cursor.lastrowid


class RecordingExecutor:
    def __init__(self, statuses=("success",)):
        self.statuses = list(statuses)
        self.calls = []

    def __call__(self, account_id, platform, **kwargs):
        self.calls.append((account_id, platform, kwargs))
        status = self.statuses.pop(0) if self.statuses else "success"
        failures = [] if status == "success" else [{"error": f"synthetic {status}"}]
        return {"status": status, "failures": failures}


def scheduler(clock, executor, accounts, backoff=(300, 900, 3600)):
    return BackgroundAccountSyncScheduler(
        interval_seconds=5,
        account_source=lambda: accounts,
        sync_executor=executor,
        clock=lambda: clock,
        backoff_seconds=backoff,
    )


def main():
    reset_test_db()
    connected_id = add_account()
    inactive_id = add_account(status="inactive")
    accounts = [
        {"id": connected_id, "platform": "youtube", "status": "connected"},
        {"id": inactive_id, "platform": "youtube", "status": "inactive"},
    ]

    due = due_accounts(now=NOW, accounts=accounts)
    assert [item["account"]["id"] for item in due] == [connected_id]
    assert due[0]["daily_date"] == "2026-09-06"

    successful = RecordingExecutor()
    first = scheduler(NOW, successful, accounts)
    outcome = first.run_once()
    assert outcome["checked"] == 1
    assert successful.calls[0][2]["analytics_windows"] == [
        ("2026-09-06", "2026-09-06"),
        (None, None),
    ]
    state = get_sync_state(connected_id, "youtube")
    assert state["scheduler_status"] == "success"
    assert state["scheduler_last_daily_date"] == "2026-09-06"
    assert state["scheduler_retry_count"] == 0
    assert state["scheduler_next_retry_at"] is None
    assert first.run_once()["checked"] == 0
    assert len(successful.calls) == 1

    retry_id = add_account()
    retry_accounts = [{"id": retry_id, "platform": "youtube", "status": "connected"}]
    failing = RecordingExecutor(("failed",))
    scheduler(NOW, failing, retry_accounts).run_once()
    failed_state = get_sync_state(retry_id, "youtube")
    assert failed_state["scheduler_status"] == "failed"
    assert failed_state["scheduler_retry_count"] == 1
    assert failed_state["scheduler_next_retry_at"] == "2026-09-07T01:05:00+00:00"
    assert due_accounts(
        now="2026-09-07T01:04:59+00:00", accounts=retry_accounts
    ) == []

    # A fresh scheduler instance reads retry state from SQLite after restart.
    failing_again = RecordingExecutor(("failed",))
    scheduler(
        datetime(2026, 9, 7, 1, 5, tzinfo=timezone.utc),
        failing_again,
        retry_accounts,
    ).run_once()
    restarted_state = get_sync_state(retry_id, "youtube")
    assert restarted_state["scheduler_retry_count"] == 2
    assert restarted_state["scheduler_next_retry_at"] == "2026-09-07T01:20:00+00:00"

    partial = RecordingExecutor(("partial",))
    scheduler(
        datetime(2026, 9, 7, 1, 20, tzinfo=timezone.utc), partial, retry_accounts
    ).run_once()
    partial_state = get_sync_state(retry_id, "youtube")
    assert partial_state["scheduler_status"] == "partial"
    assert partial_state["scheduler_retry_count"] == 3
    assert partial_state["last_error"] == "synthetic partial"

    recovered = RecordingExecutor()
    scheduler(
        datetime(2026, 9, 7, 2, 20, tzinfo=timezone.utc), recovered, retry_accounts
    ).run_once()
    recovered_state = get_sync_state(retry_id, "youtube")
    assert recovered_state["scheduler_status"] == "success"
    assert recovered_state["scheduler_retry_count"] == 0
    assert recovered_state["scheduler_next_retry_at"] is None
    assert recovered_state["last_error"] is None

    # Append-history remains intact; Query V2 chooses the newest same-day snapshot.
    for views, collected_at in (
        (10, "2026-09-07T00:05:00+00:00"),
        (12, "2026-09-07T00:10:00+00:00"),
    ):
        save_metric(
            AnalyticsMetric(
                video_id="daily-video",
                content_id="daily-content",
                platform="youtube",
                account_id=connected_id,
                source="scheduler-test",
                period_start="2026-09-06",
                period_end="2026-09-06",
                views=views,
                collected_at=collected_at,
            )
        )
    query = query_data_center(
        account_id=connected_id,
        platform="youtube",
        date_range="custom",
        start_date="2026-09-06",
        end_date="2026-09-06",
        interval="daily",
    )
    assert query["summary"]["total_views"] == 12
    assert query["time_series"]["points"][0]["metric_values"]["views"] == 12

    # start() is idempotent, so lifespan cannot create duplicate scheduler loops.
    idle = scheduler(NOW, RecordingExecutor(), [])
    idle.start()
    thread = idle._thread
    idle.start()
    assert idle._thread is thread
    idle.stop()
    assert idle.status()["running"] is False

    main_source = (BACKEND / "main.py").read_text(encoding="utf-8")
    accounts_source = (BACKEND / "routers" / "accounts.py").read_text(encoding="utf-8")
    assert "account_sync_scheduler.start()" in main_source
    assert "account_sync_scheduler.stop()" in main_source
    assert "@router.post('/accounts/{account_id}/sync-all')" in accounts_source
    assert "execute_account_sync(" in accounts_source

    print("Background daily analytics scheduler smoke test passed")
    print("due/idempotence; yesterday+28d; retry/partial/restart; Query V2 de-dup")


if __name__ == "__main__":
    main()
