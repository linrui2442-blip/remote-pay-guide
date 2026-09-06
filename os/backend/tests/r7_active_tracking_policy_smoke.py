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
from analytics.publish_bridge import collect_account_publish_metrics
from assets.manager import create_video_asset
from data.tracking import (
    get_history_summaries,
    get_tracking_records,
    refresh_tracking_policy,
    set_tracking_pinned,
)
from publish.manager import create_publish_task, update_publish_status
from publish.models import PublishTask


class FakeCollector:
    def __init__(self):
        self.calls = []

    def collect(
        self,
        video_id,
        platform,
        *,
        account_id=None,
        content_id=None,
        start_date=None,
        end_date=None,
    ):
        self.calls.append(video_id)
        return {
            "video_id": video_id,
            "platform": platform,
            "views": 1,
        }


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
    account_id = 77
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)

    # Create 12 videos in chronological order. video-12 is newest.
    for index in range(1, 13):
        published_at = (base + timedelta(days=index)).isoformat()
        add_published(account_id, f"video-{index:02d}", published_at)

    # Give the oldest video a real metric before it ages out. The transition to
    # HISTORICAL must preserve a compact lifecycle summary instead of deleting it.
    save_metric(
        AnalyticsMetric(
            video_id="video-01",
            content_id="video-01",
            platform="youtube",
            source="youtube_analytics_api_v2",
            views=321,
            watch_time=654,
            average_view_duration=18.5,
            retention=73.2,
            likes=9,
            comments=2,
            shares=1,
        )
    )

    state = refresh_tracking_policy(account_id, "youtube", active_limit=10)
    assert state["active"] == 10
    assert state["historical"] == 2
    assert state["archived"] == 0

    records = get_tracking_records(account_id, "youtube")
    by_video = {item["platform_video_id"]: item for item in records}
    assert by_video["video-12"]["state"] == "active"
    assert by_video["video-03"]["state"] == "active"
    assert by_video["video-02"]["state"] == "historical"
    assert by_video["video-01"]["state"] == "historical"

    history = get_history_summaries(account_id, "youtube")
    oldest_summary = next(
        item for item in history if item["platform_video_id"] == "video-01"
    )
    assert oldest_summary["views"] == 321
    assert oldest_summary["watch_time"] == 654
    assert oldest_summary["average_view_percentage"] == 73.2

    # Account Analytics sync must query only the active window.
    collector = FakeCollector()
    sync_result = collect_account_publish_metrics(
        account_id,
        platform="youtube",
        collector=collector,
        active_limit=10,
    )
    assert sync_result["tracking_policy"] == "latest_plus_pinned"
    assert sync_result["active_limit"] == 10
    assert sync_result["found"] == 10
    assert len(collector.calls) == 10
    assert "video-01" not in collector.calls
    assert "video-02" not in collector.calls

    # Pinning an older proven winner keeps it in the active query set without
    # changing the newest-10 policy for everything else.
    pinned = set_tracking_pinned(
        account_id,
        "youtube",
        "video-01",
        pinned=True,
        active_limit=10,
    )
    assert pinned["active"] == 11
    assert pinned["pinned"] == 1

    pinned_collector = FakeCollector()
    pinned_sync = collect_account_publish_metrics(
        account_id,
        platform="youtube",
        collector=pinned_collector,
        active_limit=10,
    )
    assert pinned_sync["found"] == 11
    assert "video-01" in pinned_collector.calls

    # Unpin returns the old item to historical state, but its summary survives.
    unpinned = set_tracking_pinned(
        account_id,
        "youtube",
        "video-01",
        pinned=False,
        active_limit=10,
    )
    assert unpinned["active"] == 10
    assert unpinned["historical"] == 2
    assert get_history_summaries(account_id, "youtube")

    print("Active tracking policy smoke test passed")
    print("Newest 10 -> ACTIVE")
    print("Older content -> HISTORICAL with compact summary")
    print("Pinned historical winner -> remains in active Analytics sync")


if __name__ == "__main__":
    main()
