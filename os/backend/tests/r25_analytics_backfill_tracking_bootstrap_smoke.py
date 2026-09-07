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
from analytics.manager import save_metric
from analytics.models import AnalyticsMetric
from assets.manager import create_video_asset
from data.tracking import get_tracking_records, set_tracking_pinned
from publish.manager import create_publish_task, update_publish_status
from publish.models import PublishTask


DB_PATH = Path("os/database/os.db")
ACCOUNT_ID = 2500


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
        conn.execute(
            "INSERT INTO accounts (id, platform, account_name, status) VALUES (?, 'youtube', 'bootstrap-test', 'connected')",
            (ACCOUNT_ID,),
        )
        conn.commit()


def add_external_video(index, published_at):
    platform_video_id = f"youtube-{index:02d}"
    content_id = f"content-{index:02d}"
    asset_id = f"asset-{index:02d}"
    url = f"https://www.youtube.com/watch?v={platform_video_id}"
    create_video_asset(
        {
            "asset_id": asset_id,
            "video_id": content_id,
            "source_provider": "youtube",
            "storage_type": "external",
            "asset_url": url,
            "status": "published",
            "metadata": {
                "title": f"External video {index}",
                "published_at": published_at,
            },
            "source": "youtube",
            "location": url,
        }
    )
    task = create_publish_task(
        PublishTask(
            asset_id=asset_id,
            video_id=content_id,
            platform="youtube",
            account_id=ACCOUNT_ID,
            status="published",
            title=f"External video {index}",
            privacy_status="public",
        )
    )
    update_publish_status(
        task["id"],
        "published",
        platform_video_id=platform_video_id,
        published_url=url,
    )


def save_snapshot(video_index, start, end):
    return save_metric(
        AnalyticsMetric(
            video_id=f"youtube-{video_index:02d}",
            content_id=f"content-{video_index:02d}",
            platform="youtube",
            account_id=ACCOUNT_ID,
            source="bootstrap-test",
            period_start=start,
            period_end=end,
            views=1,
        )
    )


def eligible_ids(plan):
    return {item["video_id"] for item in plan["eligible_videos"]}


def main():
    reset_db()
    base = datetime(2026, 8, 1, tzinfo=timezone.utc)
    for index in range(1, 13):
        add_external_video(index, (base + timedelta(days=index)).isoformat())

    # With zero Analytics rows, authoritative tracked content still bootstraps
    # a complete plan. Synced external assets are normal eligible content.
    initial = plan_backfill(
        ACCOUNT_ID, date_range="7d", end_date="2026-09-06"
    )
    assert len(initial["eligible_videos"]) == 10
    assert eligible_ids(initial) == {
        f"youtube-{index:02d}" for index in range(3, 13)
    }
    assert initial["estimated_request_count"] == 70
    assert {
        (item["video_id"], item["content_id"])
        for item in initial["eligible_videos"]
    } >= {("youtube-12", "content-12")}

    records = {
        item["platform_video_id"]: item
        for item in get_tracking_records(ACCOUNT_ID, "youtube")
    }
    assert records["youtube-01"]["state"] == "historical"
    assert records["youtube-02"]["state"] == "historical"

    pinned = set_tracking_pinned(
        ACCOUNT_ID, "youtube", "youtube-01", pinned=True
    )
    assert pinned["active"] == 11
    pinned_plan = plan_backfill(
        ACCOUNT_ID, date_range="7d", end_date="2026-09-06"
    )
    assert "youtube-01" in eligible_ids(pinned_plan)
    assert "youtube-02" not in eligible_ids(pinned_plan)

    set_tracking_pinned(ACCOUNT_ID, "youtube", "youtube-01", pinned=False)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE content_tracking SET state='archived' WHERE account_id=? AND platform_video_id='youtube-01'",
            (ACCOUNT_ID,),
        )
        conn.commit()
    lifecycle_plan = plan_backfill(
        ACCOUNT_ID, date_range="7d", end_date="2026-09-06"
    )
    assert "youtube-01" not in eligible_ids(lifecycle_plan)
    assert "youtube-02" not in eligible_ids(lifecycle_plan)

    # Only exact single-day snapshots suppress work. A 28-day aggregate never
    # masquerades as one or more daily reporting snapshots.
    save_snapshot(12, "2026-09-01", "2026-09-01")
    save_snapshot(11, "2026-08-10", "2026-09-06")
    with_existing = plan_backfill(
        ACCOUNT_ID, date_range="7d", end_date="2026-09-06"
    )
    by_video = {
        item["video_id"]: item for item in with_existing["eligible_videos"]
    }
    assert by_video["youtube-12"]["existing_dates"] == ["2026-09-01"]
    assert "2026-09-01" not in by_video["youtube-12"]["missing_dates"]
    assert by_video["youtube-11"]["existing_dates"] == []
    assert len(by_video["youtube-11"]["missing_dates"]) == 7
    assert with_existing["estimated_request_count"] == 69

    print("Analytics backfill tracking bootstrap smoke test passed")
    print("zero-metric bootstrap; daily skip; aggregate isolation; latest-10+pinned; lifecycle; external assets")


if __name__ == "__main__":
    main()
