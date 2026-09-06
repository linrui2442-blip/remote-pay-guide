import os
import sqlite3
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
from data.tracking import (
    archive_stale_historical,
    get_history_summaries,
    get_tracking_records,
    refresh_tracking_policy,
)
from publish.manager import create_publish_task, update_publish_status
from publish.models import PublishTask


def reset_test_db():
    Path("os/database").mkdir(parents=True, exist_ok=True)
    db = Path("os/database/os.db")
    if db.exists():
        db.unlink()


def add_published(account_id, video_id, published_at):
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
                "title": f"Title {video_id}",
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
            title=f"Title {video_id}",
            privacy_status="public",
        )
    )
    update_publish_status(
        task["id"],
        "published",
        platform_video_id=video_id,
        published_url=f"https://example.invalid/{video_id}",
    )


def main():
    reset_test_db()
    account_id = 88
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # Twelve videos means the oldest two leave the default newest-10 window.
    for index in range(1, 13):
        add_published(
            account_id,
            f"video-{index:02d}",
            (base + timedelta(days=index)).isoformat(),
        )

    # Keep a compact final summary for the oldest item before it becomes stale.
    save_metric(
        AnalyticsMetric(
            video_id="video-01",
            content_id="video-01",
            platform="youtube",
            account_id=account_id,
            source="youtube_analytics_api",
            views=45,
            watch_time=300,
            average_view_duration=12.5,
            retention=58.0,
            likes=2,
            comments=0,
            shares=0,
        )
    )

    initial = refresh_tracking_policy(account_id, "youtube", active_limit=10)
    assert initial["active"] == 10
    assert initial["historical"] == 2
    assert initial["archived"] == 0

    # Simulate that both historical items left ACTIVE more than 90 days ago.
    stale_time = datetime(2026, 4, 1, tzinfo=timezone.utc) - timedelta(days=100)
    with sqlite3.connect("os/database/os.db") as conn:
        conn.execute(
            """
            UPDATE content_tracking
            SET left_active_at=?
            WHERE account_id=? AND state='historical'
            """,
            (stale_time.isoformat(), account_id),
        )
        conn.commit()

    archived = archive_stale_historical(
        account_id,
        "youtube",
        archive_after_days=90,
        now=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    assert archived["archived"] == 2

    records = get_tracking_records(account_id, "youtube")
    by_video = {item["platform_video_id"]: item for item in records}
    assert by_video["video-01"]["state"] == "archived"
    assert by_video["video-02"]["state"] == "archived"

    # Refreshing the newest-10 policy must not accidentally resurrect ARCHIVED
    # content back into HISTORICAL.
    refreshed = refresh_tracking_policy(account_id, "youtube", active_limit=10)
    assert refreshed["archived"] == 2
    assert refreshed["historical"] == 0

    history = get_history_summaries(account_id, "youtube")
    summary = next(item for item in history if item["platform_video_id"] == "video-01")
    assert summary["views"] == 45
    assert summary["average_view_percentage"] == 58.0

    archived_view = query_data_center(
        account_id=account_id,
        platform="youtube",
        scope="archived",
        sort_by="views",
    )
    assert archived_view["total_matching"] == 2
    assert archived_view["rows"][0]["tracking_state"] == "archived"
    assert archived_view["rows"][0]["platform_video_id"] == "video-01"
    assert archived_view["rows"][0]["views"] == 45

    active_view = query_data_center(
        account_id=account_id,
        platform="youtube",
        scope="active",
    )
    assert active_view["total_matching"] == 0  # no Analytics snapshots for newest 10

    print("Archive tracking policy smoke test passed")
    print("ACTIVE -> HISTORICAL -> ARCHIVED")
    print("ARCHIVED keeps compact lifecycle summary and stays queryable")


if __name__ == "__main__":
    main()
