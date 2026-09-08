from test_database_helper import TEST_DATABASE_PATH, assert_safe_test_database_path
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)
os.environ["OS_DISABLE_BACKGROUND_ACCOUNT_SYNC"] = "1"
os.environ["OS_DISABLE_ANALYTICS_BACKFILL_WORKER"] = "1"

from analytics.backfill import plan_backfill
from analytics.backfill_runtime import AnalyticsBackfillWorker, create_operation, get_operation
from analytics.errors import AnalyticsNoData
from analytics.manager import get_account_metrics, save_metric
from analytics.models import AnalyticsMetric
from analytics.publish_bridge import collect_account_publish_metrics
from analytics.youtube_api import YouTubeAnalyticsAPIClient
from data.query import query_data_center
from data.sync_state import get_backfill_no_data_coverage
from publish.manager import create_publish_task, update_publish_status
from publish.models import PublishTask


DB_PATH = TEST_DATABASE_PATH
ACCOUNT_ID = 2700


def reset_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE accounts (
                id INTEGER PRIMARY KEY, platform TEXT, account_name TEXT,
                status TEXT, access_token TEXT, refresh_token TEXT,
                created_at TEXT, updated_at TEXT)"""
        )
        conn.execute(
            "INSERT INTO accounts (id, platform, account_name, status) VALUES (?, 'youtube', 'no-data-test', 'connected')",
            (ACCOUNT_ID,),
        )
        conn.commit()


def add_published(index):
    task = create_publish_task(
        PublishTask(
            asset_id=f"asset-{index}", video_id=f"content-{index}",
            platform="youtube", account_id=ACCOUNT_ID, status="published",
            scheduled_time=f"2026-09-{index:02d}T00:00:00+00:00",
        )
    )
    update_publish_status(task["id"], "published", platform_video_id=f"video-{index}")


class EmptyService:
    def reports(self): return self
    def query(self, **kwargs): return self
    def execute(self): return {"columnHeaders": [{"name": "views"}]}


class NoDataCollector:
    def collect(self, video_id, platform, **kwargs):
        raise AnalyticsNoData(f"no row for {video_id}")


class MixedCollector:
    def __init__(self, failures=0):
        self.index = 0
        self.failures = failures

    def collect_account(self, platform, account_id=None, **kwargs):
        return {"period_end": kwargs.get("end_date"), "metrics": {"views": 1}}

    def collect(self, video_id, platform, **kwargs):
        self.index += 1
        if self.index <= 3:
            return {"period_end": kwargs.get("end_date"), "views": 1}
        if self.index > 10 - self.failures:
            raise RuntimeError("synthetic network failure")
        raise AnalyticsNoData(f"no row for {video_id}")


def main():
    test_now = datetime.now(timezone.utc)
    reset_db()
    for index in range(1, 11):
        add_published(index)

    client = YouTubeAnalyticsAPIClient(service=EmptyService())
    try:
        client.collect_video_metrics("video-10", "2026-09-06", "2026-09-06")
        raise AssertionError("missing provider rows must have a typed outcome")
    except AnalyticsNoData:
        pass
    try:
        client.collect_channel_metrics("2026-09-06", "2026-09-06")
        raise AssertionError("channel no-data must not become a zero metric")
    except AnalyticsNoData:
        pass
    assert get_account_metrics(ACCOUNT_ID, platform="youtube") == []

    operation = create_operation(
        ACCOUNT_ID, platform="youtube", date_range="custom",
        start_date="2026-09-06", end_date="2026-09-06",
    )
    finished = AnalyticsBackfillWorker(
        batch_size=10, collector=NoDataCollector(),
        clock=lambda: test_now,
    ).process_once()
    assert finished["operation_id"] == operation["operation_id"]
    assert finished["status"] == "success"
    assert finished["completed_work"] == 10
    assert finished["no_data_work"] == 10
    assert finished["failed_work"] == 0
    assert finished["remaining_work"] == 0
    assert finished["last_error"] is None
    assert get_account_metrics(ACCOUNT_ID, platform="youtube") == []

    coverage = get_backfill_no_data_coverage(ACCOUNT_ID, "youtube")
    assert len(coverage) == 10
    restarted_plan = plan_backfill(
        ACCOUNT_ID, date_range="custom", start_date="2026-09-06",
        end_date="2026-09-06", today=test_now.date(),
    )
    assert restarted_plan["estimated_request_count"] == 0
    assert all(item["observed_no_data_dates"] == ["2026-09-06"] for item in restarted_plan["eligible_videos"])

    # Expired recent coverage is queried again after the 24-hour TTL.
    expired_at = (test_now - timedelta(hours=25)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        raw = conn.execute(
            "SELECT backfill_no_data_coverage FROM platform_sync_state WHERE account_id=? AND platform='youtube'",
            (ACCOUNT_ID,),
        ).fetchone()[0]
        conn.execute(
            "UPDATE platform_sync_state SET backfill_no_data_coverage=replace(backfill_no_data_coverage, ?, ?)",
            (test_now.isoformat(), expired_at),
        )
        conn.commit()
    expired_plan = plan_backfill(
        ACCOUNT_ID, date_range="custom", start_date="2026-09-06",
        end_date="2026-09-06", today=test_now.date(),
    )
    assert expired_plan["estimated_request_count"] == 10

    # A real daily snapshot wins over no-data coverage; a 28-day aggregate does not.
    save_metric(AnalyticsMetric(
        video_id="video-10", content_id="content-10", platform="youtube",
        account_id=ACCOUNT_ID, source="test", period_start="2026-09-06",
        period_end="2026-09-06", views=5,
    ))
    save_metric(AnalyticsMetric(
        video_id="video-9", content_id="content-9", platform="youtube",
        account_id=ACCOUNT_ID, source="test", period_start="2026-08-10",
        period_end="2026-09-06", views=280,
    ))
    real_plan = plan_backfill(
        ACCOUNT_ID, date_range="custom", start_date="2026-09-06",
        end_date="2026-09-06", today=test_now.date(),
    )
    indexed = {item["video_id"]: item for item in real_plan["eligible_videos"]}
    assert indexed["video-10"]["existing_dates"] == ["2026-09-06"]
    assert indexed["video-10"]["missing_dates"] == []
    assert indexed["video-9"]["existing_dates"] == []
    assert indexed["video-9"]["missing_dates"] == ["2026-09-06"]

    query = query_data_center(
        account_id=ACCOUNT_ID, platform="youtube", date_range="custom",
        start_date="2026-09-06", end_date="2026-09-06", interval="daily",
    )
    assert query["summary"]["total_views"] == 5
    assert len(query["time_series"]["points"]) == 1

    success = collect_account_publish_metrics(
        ACCOUNT_ID, platform="youtube", collector=MixedCollector(failures=0),
        start_date="2026-09-06", end_date="2026-09-06",
    )
    assert success["collected"] == 3 and success["no_data"] == 7
    assert success["failed"] == 0
    assert success["sync_state"]["analytics_status"] == "success"

    partial = collect_account_publish_metrics(
        ACCOUNT_ID, platform="youtube", collector=MixedCollector(failures=1),
        start_date="2026-09-06", end_date="2026-09-06",
    )
    assert partial["collected"] == 3 and partial["no_data"] == 6
    assert partial["failed"] == 1
    assert partial["sync_state"]["analytics_status"] == "partial"

    assert get_operation(operation["operation_id"])["status"] == "success"
    print("Analytics no-data observation smoke test passed")
    print("typed no-data; durable TTL coverage; operation progress; scheduler semantics; no fake Query V2 points")


if __name__ == "__main__":
    main()
