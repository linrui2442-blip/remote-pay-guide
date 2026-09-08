from test_database_helper import TEST_DATABASE_PATH, assert_safe_test_database_path
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from analytics.publish_bridge import collect_account_publish_metrics
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
        self.calls.append(
            {
                "video_id": video_id,
                "platform": platform,
                "account_id": account_id,
                "content_id": content_id,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        if video_id == "video-fail":
            raise RuntimeError("simulated platform failure")
        return {
            "video_id": video_id,
            "platform": platform,
            "views": 123,
            "retention": 62.5,
        }


def reset_test_db():
    db = TEST_DATABASE_PATH
    if db.exists():
        db.unlink()


def add_published(account_id, video_id, platform="youtube"):
    task = create_publish_task(
        PublishTask(
            asset_id=f"asset-{video_id}",
            video_id=video_id,
            platform=platform,
            account_id=account_id,
            status="published",
            title=video_id,
            privacy_status="public",
        )
    )
    update_publish_status(
        task["id"],
        "published",
        platform_video_id=video_id,
        published_url=f"https://example.invalid/{video_id}",
    )
    return task["id"]


def main():
    reset_test_db()
    add_published(7, "video-ok")
    add_published(7, "video-fail")
    add_published(8, "other-account")
    add_published(7, "other-platform", platform="instagram")

    create_publish_task(
        PublishTask(
            asset_id="asset-pending",
            video_id="pending",
            platform="youtube",
            account_id=7,
            status="pending",
        )
    )

    collector = FakeCollector()
    result = collect_account_publish_metrics(
        7,
        platform="youtube",
        collector=collector,
        start_date="2026-08-01",
        end_date="2026-08-28",
    )

    assert result["account_id"] == 7
    assert result["platform"] == "youtube"
    assert result["found"] == 2
    assert result["collected"] == 1
    assert result["failed"] == 1
    assert result["results"][0]["video_id"] == "video-ok"
    assert result["failures"][0]["video_id"] == "video-fail"
    assert "simulated platform failure" in result["failures"][0]["error"]

    assert len(collector.calls) == 2
    assert all(call["account_id"] == 7 for call in collector.calls)
    assert all(call["platform"] == "youtube" for call in collector.calls)
    assert all(call["start_date"] == "2026-08-01" for call in collector.calls)
    assert all(call["end_date"] == "2026-08-28" for call in collector.calls)

    print("Account-level Analytics sync smoke test passed")
    print("Published account tasks -> batch collector")
    print("Other accounts/platforms/pending tasks -> ignored")
    print("One task failure -> other videos still collected")


if __name__ == "__main__":
    main()
