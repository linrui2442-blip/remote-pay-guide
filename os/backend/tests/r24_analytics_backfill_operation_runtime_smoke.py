import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)
os.environ["OS_DISABLE_BACKGROUND_ACCOUNT_SYNC"] = "1"
os.environ["OS_DISABLE_ANALYTICS_BACKFILL_WORKER"] = "1"

from analytics.backfill_runtime import (
    AnalyticsBackfillWorker,
    cancel_operation,
    create_operation,
    get_operation,
    list_operations,
    recover_operations,
)
from analytics.manager import get_account_video_metrics, save_metric
from analytics.models import AnalyticsMetric
from data.query import query_data_center
from integrations.sync_scheduler import due_accounts
from routers.analytics import router


DB_PATH = Path("os/database/os.db")


def reset_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY, platform TEXT, account_name TEXT,
                status TEXT, access_token TEXT, refresh_token TEXT,
                created_at TEXT, updated_at TEXT
            )
            """
        )


def seed(account_id, video_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO accounts (id, platform, account_name, status) VALUES (?, 'youtube', ?, 'connected')",
            (account_id, f"account-{account_id}"),
        )
        conn.commit()
    save_metric(
        AnalyticsMetric(
            video_id=video_id,
            content_id=f"content-{video_id}",
            platform="youtube",
            account_id=account_id,
            source="operation-seed",
            period_start="2026-08-01",
            period_end="2026-08-28",
            views=280,
        )
    )


class FakeCollector:
    def __init__(self, operation_id=None, fail_dates=None, cancel_during=False):
        self.operation_id = operation_id
        self.fail_dates = set(fail_dates or [])
        self.calls = []
        self.observed_statuses = []
        self.cancel_during = cancel_during

    def collect(
        self, video_id, platform, *, account_id=None, content_id=None,
        start_date=None, end_date=None,
    ):
        if self.operation_id:
            self.observed_statuses.append(get_operation(self.operation_id)["status"])
        self.calls.append((video_id, start_date))
        if start_date in self.fail_dates:
            raise RuntimeError("synthetic API failure access_token=must-not-leak")
        metric = save_metric(
            AnalyticsMetric(
                video_id=video_id,
                content_id=content_id,
                platform=platform,
                account_id=account_id,
                source="operation-fake",
                period_start=start_date,
                period_end=end_date,
                views=int(start_date[-2:]),
            )
        )
        if self.cancel_during:
            cancel_operation(self.operation_id)
            self.cancel_during = False
        return metric


def worker(collector, now, batch_size=2):
    return AnalyticsBackfillWorker(
        interval_seconds=2,
        batch_size=batch_size,
        collector=collector,
        clock=lambda: now,
    )


def main():
    reset_db()
    seed(2400, "video-a")
    operation = create_operation(
        2400,
        platform="youtube",
        date_range="custom",
        start_date="2026-09-01",
        end_date="2026-09-05",
    )
    assert operation["status"] == "queued"
    assert operation["total_work"] == 5
    assert operation["completed_work"] == 0

    try:
        create_operation(
            2400, date_range="custom",
            start_date="2026-09-01", end_date="2026-09-05",
        )
        raise AssertionError("duplicate active operation must be rejected")
    except ValueError as exc:
        assert "already exists" in str(exc)

    collector = FakeCollector(operation["operation_id"])
    runtime = worker(
        collector,
        datetime(2026, 9, 7, 3, 0, tzinfo=timezone.utc),
        batch_size=2,
    )
    first_batch = runtime.process_once()
    assert collector.observed_statuses == ["running", "running"]
    assert first_batch["status"] == "queued"
    assert first_batch["completed_work"] == 2
    assert first_batch["remaining_work"] == 3
    assert first_batch["progress_percentage"] == 40.0
    assert len(collector.calls) == 2

    runtime.process_once()
    completed = runtime.process_once()
    assert completed["status"] == "success"
    assert completed["completed_work"] == 5
    assert completed["remaining_work"] == 0
    assert completed["finished_at"]

    history = get_account_video_metrics(2400, "video-a", platform="youtube")
    assert len([item for item in history if item["period_start"] == item["period_end"]]) == 5
    assert runtime.process_once() is None
    assert len(collector.calls) == 5
    query = query_data_center(
        account_id=2400, platform="youtube", date_range="custom",
        start_date="2026-09-01", end_date="2026-09-05", interval="daily",
    )
    assert query["time_series"]["available"] is True
    assert [point["metric_values"]["views"] for point in query["time_series"]["points"]] == [1, 2, 3, 4, 5]

    seed(2401, "video-b")
    partial_op = create_operation(
        2401, date_range="custom",
        start_date="2026-09-01", end_date="2026-09-02",
    )
    partial = worker(
        FakeCollector(fail_dates={"2026-09-02"}),
        datetime(2026, 9, 7, 4, 0, tzinfo=timezone.utc),
    ).process_once()
    assert partial["operation_id"] == partial_op["operation_id"]
    assert partial["status"] == "partial"
    assert partial["completed_work"] == 1
    assert partial["failed_work"] == 1
    assert partial["next_retry_at"] == "2026-09-07T04:05:00+00:00"
    assert "must-not-leak" not in (partial["last_error"] or "")

    resumed = worker(
        FakeCollector(),
        datetime(2026, 9, 7, 4, 5, tzinfo=timezone.utc),
    ).process_once()
    assert resumed["status"] == "success"
    assert resumed["completed_work"] == 2

    seed(2402, "video-c")
    failed_op = create_operation(
        2402, date_range="custom",
        start_date="2026-09-01", end_date="2026-09-01",
    )
    failed = worker(
        FakeCollector(fail_dates={"2026-09-01"}),
        datetime(2026, 9, 7, 5, 0, tzinfo=timezone.utc),
    ).process_once()
    assert failed["operation_id"] == failed_op["operation_id"]
    assert failed["status"] == "failed"
    assert failed["retry_count"] == 1
    assert failed["next_retry_at"] == "2026-09-07T05:05:00+00:00"

    cancelled = cancel_operation(failed_op["operation_id"])
    assert cancelled["status"] == "cancelled"
    assert cancelled["finished_at"]
    assert worker(FakeCollector(), datetime(2026, 9, 7, 5, 5, tzinfo=timezone.utc)).process_once() is None

    seed(2404, "video-e")
    running_cancel_op = create_operation(
        2404, date_range="custom",
        start_date="2026-09-01", end_date="2026-09-02",
    )
    cancelled_during_work = worker(
        FakeCollector(
            operation_id=running_cancel_op["operation_id"], cancel_during=True
        ),
        datetime(2026, 9, 7, 5, 30, tzinfo=timezone.utc),
        batch_size=1,
    ).process_once()
    assert cancelled_during_work["status"] == "cancelled"
    assert cancelled_during_work["completed_work"] == 1
    assert cancelled_during_work["remaining_work"] == 1

    seed(2403, "video-d")
    restart_op = create_operation(
        2403, date_range="custom",
        start_date="2026-09-01", end_date="2026-09-01",
    )
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE analytics_backfill_operations SET status='running' WHERE id=?",
            (restart_op["operation_id"],),
        )
        conn.commit()
    recover_operations()
    assert get_operation(restart_op["operation_id"])["status"] == "queued"
    assert worker(FakeCollector(), datetime(2026, 9, 7, 6, 0, tzinfo=timezone.utc)).process_once()["status"] == "success"

    assert len(list_operations(account_id=2400)) == 1
    account = {"id": 2400, "platform": "youtube", "status": "connected"}
    assert due_accounts(now="2026-09-07T07:00:00+00:00", accounts=[account])

    idle = AnalyticsBackfillWorker(interval_seconds=2, collector=FakeCollector())
    os.environ.pop("OS_DISABLE_ANALYTICS_BACKFILL_WORKER", None)
    idle.start()
    thread = idle._thread
    idle.start()
    assert idle._thread is thread
    idle.stop()
    assert idle.status()["running"] is False

    paths = {route.path for route in router.routes}
    assert "/analytics/backfill/operations/{account_id}" in paths
    assert "/analytics/backfill/operations/{operation_id}" in paths
    assert "/analytics/backfill/operations/{operation_id}/cancel" in paths
    main_source = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "analytics_backfill_worker.start()" in main_source
    assert "analytics_backfill_worker.stop()" in main_source

    print("Analytics backfill operation runtime smoke test passed")
    print("async create; batches; progress; retry/resume/cancel; Query V2; singleton")


if __name__ == "__main__":
    main()
