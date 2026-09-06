import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from analytics.manager import save_metric
from analytics.models import AnalyticsMetric
from assets.manager import create_video_asset
from data.query import query_data_center
from data.tracking import refresh_tracking_policy
from publish.manager import create_publish_task, update_publish_status
from publish.models import PublishTask


def reset_test_db():
    Path("os/database").mkdir(parents=True, exist_ok=True)
    db = Path("os/database/os.db")
    if db.exists():
        db.unlink()


def add_video(account_id, index, published_at):
    video_id = f"query-video-{index:02d}"
    asset_id = f"asset-{video_id}"
    create_video_asset(
        {
            "asset_id": asset_id,
            "video_id": video_id,
            "source_provider": "youtube",
            "storage_type": "external",
            "asset_url": f"https://example.invalid/{video_id}",
            "status": "published",
            "metadata": {
                "title": f"Query Video {index:02d}",
                "published_at": published_at,
            },
            "source": "youtube",
            "location": f"https://example.invalid/{video_id}",
        }
    )
    task = create_publish_task(
        PublishTask(
            asset_id=asset_id,
            video_id=video_id,
            platform="youtube",
            account_id=account_id,
            status="published",
            title=f"Query Video {index:02d}",
            privacy_status="public",
        )
    )
    update_publish_status(
        task["id"],
        "published",
        platform_video_id=video_id,
        published_url=f"https://example.invalid/{video_id}",
    )
    save_metric(
        AnalyticsMetric(
            video_id=video_id,
            content_id=video_id,
            platform="youtube",
            account_id=account_id,
            source="youtube_analytics_api",
            period_start="2026-08-09",
            period_end="2026-09-05",
            views=index * 10,
            watch_time=index * 100,
            average_view_duration=float(index),
            retention=40.0 + index,
            likes=index,
            shares=index // 2,
        )
    )


def main():
    reset_test_db()
    account_id = 88
    base = datetime(2026, 8, 1, tzinfo=timezone.utc)
    for index in range(1, 13):
        add_video(
            account_id,
            index,
            (base + timedelta(days=index)).isoformat(),
        )

    refresh_tracking_policy(account_id, "youtube", active_limit=10)

    active = query_data_center(
        account_id=account_id,
        platform="youtube",
        scope="active",
        sort_by="views",
        sort_direction="desc",
        limit=100,
    )
    assert active["summary"]["content_count"] == 10
    assert active["returned"] == 10
    assert active["rows"][0]["video_id"] == "query-video-12"
    assert active["rows"][-1]["video_id"] == "query-video-03"
    assert active["rows"][0]["title"] == "Query Video 12"
    assert active["rows"][0]["period_start"] == "2026-08-09"
    assert active["rows"][0]["period_end"] == "2026-09-05"
    assert active["summary"]["total_views"] == sum(index * 10 for index in range(3, 13))

    historical = query_data_center(
        account_id=account_id,
        platform="youtube",
        scope="historical",
        sort_by="views",
    )
    assert historical["summary"]["content_count"] == 2
    assert {row["video_id"] for row in historical["rows"]} == {
        "query-video-01",
        "query-video-02",
    }

    all_rows = query_data_center(
        account_id=account_id,
        platform="youtube",
        scope="all",
        sort_by="published_at",
        sort_direction="desc",
    )
    assert all_rows["summary"]["content_count"] == 12
    assert all_rows["rows"][0]["video_id"] == "query-video-12"

    print("Unified Data Center query layer smoke test passed")
    print("Active scope -> latest tracking window")
    print("Historical scope -> compact retained outcomes")
    print("All scope -> no duplicate active/history rows")


if __name__ == "__main__":
    main()
