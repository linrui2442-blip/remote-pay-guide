from test_database_helper import TEST_DATABASE_PATH, assert_safe_test_database_path
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

from analytics.backfill import (
    BackfillValidationError,
    get_backfill_status,
    plan_backfill,
    run_backfill,
)
from analytics.errors import AnalyticsNoData
from analytics.manager import get_account_video_metrics, save_metric
from analytics.models import AnalyticsMetric
from analytics.youtube_api import YouTubeAnalyticsAPIClient
from assets.manager import create_video_asset
from data.query import query_data_center
from integrations.sync_scheduler import due_accounts
from publish.manager import create_publish_task, update_publish_status
from publish.models import PublishTask
from routers.analytics import router


DB_PATH = TEST_DATABASE_PATH
ACCOUNT_ID = 2300


def reset_test_db():
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
        conn.execute(
            "INSERT INTO accounts (id, platform, account_name, status) VALUES (?, 'youtube', 'backfill-test', 'connected')",
            (ACCOUNT_ID,),
        )
        conn.commit()


def save_window(start, end, views, collected_at):
    return save_metric(
        AnalyticsMetric(
            video_id="video-1",
            content_id="content-1",
            platform="youtube",
            account_id=ACCOUNT_ID,
            source="backfill-test",
            period_start=start,
            period_end=end,
            views=views,
            collected_at=collected_at,
        )
    )


def seed_tracked_video():
    create_video_asset(
        {
            "asset_id": "asset-video-1",
            "video_id": "content-1",
            "source_provider": "youtube",
            "storage_type": "external",
            "asset_url": "https://example.invalid/video-1",
            "status": "published",
            "metadata": {"published_at": "2026-08-01T00:00:00+00:00"},
            "source": "youtube",
            "location": "https://example.invalid/video-1",
        }
    )
    task = create_publish_task(
        PublishTask(
            asset_id="asset-video-1",
            video_id="content-1",
            platform="youtube",
            account_id=ACCOUNT_ID,
            status="published",
        )
    )
    update_publish_status(
        task["id"],
        "published",
        platform_video_id="video-1",
        published_url="https://example.invalid/video-1",
    )


class FakeCollector:
    def __init__(self, fail_once=None):
        self.fail_once = set(fail_once or [])
        self.calls = []

    def collect(
        self, video_id, platform, *, account_id=None, content_id=None,
        start_date=None, end_date=None,
    ):
        assert start_date == end_date
        self.calls.append((video_id, start_date))
        if start_date in self.fail_once:
            self.fail_once.remove(start_date)
            raise RuntimeError("synthetic provider failure")
        return save_metric(
            AnalyticsMetric(
                video_id=video_id,
                content_id=content_id,
                platform=platform,
                account_id=account_id,
                source="fake-youtube-reporting-day",
                period_start=start_date,
                period_end=end_date,
                views=int(start_date[-2:]),
            )
        )


class EmptyReportService:
    def reports(self):
        return self

    def query(self, **kwargs):
        return self

    def execute(self):
        return {"columnHeaders": [{"name": "views"}]}


def main():
    reset_test_db()
    seed_tracked_video()
    save_window("2026-08-10", "2026-09-06", 2800, "2026-09-07T00:00:00+00:00")
    save_window("2026-09-01", "2026-09-01", 1, "2026-09-02T00:00:00+00:00")
    save_window("2026-09-01", "2026-09-01", 1, "2026-09-02T01:00:00+00:00")

    seven = plan_backfill(
        ACCOUNT_ID, date_range="7d", end_date="2026-09-06"
    )
    assert seven["period"]["days"] == 7
    assert seven["existing_dates"] == ["2026-09-01"]
    assert seven["missing_dates"] == [
        "2026-08-31", "2026-09-02", "2026-09-03",
        "2026-09-04", "2026-09-05", "2026-09-06",
    ]
    assert seven["estimated_request_count"] == 6
    assert seven["reporting_timezone"] == "America/Los_Angeles"
    assert "Pacific time" in seven["reporting_date_semantics"]

    twenty_eight = plan_backfill(
        ACCOUNT_ID, date_range="28d", end_date="2026-09-06"
    )
    assert twenty_eight["period"]["days"] == 28
    assert twenty_eight["estimated_request_count"] == 27

    custom = plan_backfill(
        ACCOUNT_ID,
        date_range="custom",
        start_date="2026-09-01",
        end_date="2026-09-03",
    )
    assert custom["period"]["days"] == 3
    assert custom["estimated_request_count"] == 2

    try:
        plan_backfill(
            ACCOUNT_ID,
            date_range="custom",
            start_date="2026-06-01",
            end_date="2026-09-01",
        )
        raise AssertionError("a window over 90 days must be rejected")
    except BackfillValidationError as exc:
        assert "90 days" in str(exc)

    try:
        YouTubeAnalyticsAPIClient(service=EmptyReportService()).collect_video_metrics(
            "video-1", "2026-09-01", "2026-09-01"
        )
        raise AssertionError("an absent provider row must not become a zero snapshot")
    except AnalyticsNoData as exc:
        assert "returned no row" in str(exc)

    first_collector = FakeCollector(fail_once={"2026-09-03"})
    first = run_backfill(
        ACCOUNT_ID,
        date_range="7d",
        end_date="2026-09-06",
        collector=first_collector,
        now=datetime(2026, 9, 7, 2, 0, tzinfo=timezone.utc),
    )
    assert first["status"] == "partial"
    assert first["attempted"] == 6
    assert len(first["completed"]) == 5
    assert len(first["failures"]) == 1
    assert ("video-1", "2026-09-01") not in first_collector.calls
    assert first["state"]["backfill_retry_count"] == 1
    assert first["state"]["backfill_next_retry_at"] == "2026-09-07T02:05:00+00:00"

    # State and completed snapshots survive a new service call/process instance.
    recovered_status = get_backfill_status(ACCOUNT_ID)
    assert recovered_status["state"]["backfill_status"] == "partial"
    resumed_collector = FakeCollector()
    resumed = run_backfill(
        ACCOUNT_ID,
        date_range="7d",
        end_date="2026-09-06",
        collector=resumed_collector,
        now=datetime(2026, 9, 7, 2, 5, tzinfo=timezone.utc),
    )
    assert resumed["status"] == "success"
    assert resumed_collector.calls == [("video-1", "2026-09-03")]
    assert resumed["state"]["backfill_retry_count"] == 0
    assert resumed["state"]["backfill_next_retry_at"] is None
    assert resumed["state"]["backfill_error"] is None

    # Append history is preserved, while Query V2 consumes one latest snapshot/day.
    history = get_account_video_metrics(ACCOUNT_ID, "video-1", platform="youtube")
    assert len([item for item in history if item["period_start"] == "2026-09-01"]) == 2
    query = query_data_center(
        account_id=ACCOUNT_ID,
        platform="youtube",
        date_range="7d",
        end_date="2026-09-06",
        interval="daily",
    )
    assert query["time_series"]["available"] is True
    assert len(query["time_series"]["points"]) == 7
    assert all(point["snapshot_count"] == 1 for point in query["time_series"]["points"])
    assert query["summary"]["total_views"] == sum([31, 1, 2, 3, 4, 5, 6])
    assert query["summary"]["total_views"] != 2800
    assert query["snapshot_semantics"]["overlapping_windows_summed"] is False

    account = {"id": ACCOUNT_ID, "platform": "youtube", "status": "connected"}
    assert due_accounts(now="2026-09-07T03:00:00+00:00", accounts=[account])

    paths = {route.path for route in router.routes}
    assert "/analytics/backfill/status/{account_id}" in paths
    assert "/analytics/backfill/plan/{account_id}" in paths
    assert "/analytics/backfill/run/{account_id}" in paths

    print("Historical daily analytics backfill smoke test passed")
    print("plan/missing-day; cap; partial/retry/resume; Query V2; scheduler isolation")


if __name__ == "__main__":
    main()
