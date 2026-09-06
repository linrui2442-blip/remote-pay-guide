import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from analytics.publish_bridge import collect_account_publish_metrics
from data.sync_state import get_sync_state
from integrations.youtube import YouTubeContentSync


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self, *args, **kwargs):
        return self.payload


class FakeChannels:
    def list(self, **kwargs):
        return FakeRequest(
            {
                "items": [
                    {
                        "id": "channel-sync",
                        "snippet": {"title": "Sync State Channel"},
                        "contentDetails": {
                            "relatedPlaylists": {"uploads": "uploads-sync"}
                        },
                    }
                ]
            }
        )


class FakePlaylistItems:
    def list(self, **kwargs):
        return FakeRequest(
            {
                "items": [
                    {
                        "contentDetails": {"videoId": "video-new"},
                        "snippet": {
                            "title": "Newest Video",
                            "publishedAt": "2026-09-05T00:00:00Z",
                        },
                    },
                    {
                        "contentDetails": {"videoId": "video-old"},
                        "snippet": {
                            "title": "Older Video",
                            "publishedAt": "2026-09-04T00:00:00Z",
                        },
                    },
                ]
            }
        )


class FakeVideos:
    def __init__(self, service):
        self.service = service

    def list(self, **kwargs):
        self.service.video_detail_calls += 1
        ids = kwargs["id"].split(",") if kwargs.get("id") else []
        return FakeRequest(
            {
                "items": [
                    {
                        "id": video_id,
                        "snippet": {
                            "title": "Newest Video" if video_id == "video-new" else "Older Video",
                            "publishedAt": (
                                "2026-09-05T00:00:00Z"
                                if video_id == "video-new"
                                else "2026-09-04T00:00:00Z"
                            ),
                        },
                        "status": {"privacyStatus": "public"},
                    }
                    for video_id in ids
                ]
            }
        )


class FakeYouTubeService:
    def __init__(self):
        self.video_detail_calls = 0

    def channels(self):
        return FakeChannels()

    def playlistItems(self):
        return FakePlaylistItems()

    def videos(self):
        return FakeVideos(self)


class FakeCollector:
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
        return {
            "video_id": video_id,
            "platform": platform,
            "account_id": account_id,
            "content_id": content_id,
            "period_start": start_date or "2026-08-09",
            "period_end": end_date or "2026-09-05",
            "views": 10,
        }


class FailingCollector:
    def collect(self, *args, **kwargs):
        raise RuntimeError("simulated analytics provider failure")


def reset_test_db():
    Path("os/database").mkdir(parents=True, exist_ok=True)
    db = Path("os/database/os.db")
    if db.exists():
        db.unlink()


def main():
    reset_test_db()
    account_id = 501
    service = FakeYouTubeService()
    sync = YouTubeContentSync(service=service)

    first = sync.sync(account_id, max_results=10)
    assert first["sync_mode"] == "incremental"
    assert first["previous_cursor"] is None
    assert first["content_cursor"] == "video-new"
    assert first["processed"] == 2
    assert first["imported"] == 2
    assert service.video_detail_calls == 1

    state = get_sync_state(account_id, "youtube")
    assert state["content_status"] == "success"
    assert state["content_cursor"] == "video-new"
    assert state["last_content_sync_at"]
    assert state["last_success_at"]

    second = sync.sync(account_id, max_results=10)
    assert second["previous_cursor"] == "video-new"
    assert second["processed"] == 0
    assert second["unchanged"] == 2
    assert second["already_present"] == 2
    assert service.video_detail_calls == 1

    repaired = sync.sync(account_id, max_results=10, sync_mode="full_refresh")
    assert repaired["processed"] == 2
    assert repaired["refreshed"] == 2
    assert repaired["imported"] == 0
    assert service.video_detail_calls == 2

    analytics = collect_account_publish_metrics(
        account_id,
        platform="youtube",
        collector=FakeCollector(),
        active_limit=10,
    )
    assert analytics["collected"] == 2
    assert analytics["failed"] == 0
    assert analytics["analytics_cursor"] == "2026-09-05"
    assert analytics["sync_state"]["analytics_status"] == "success"
    assert analytics["sync_state"]["analytics_cursor"] == "2026-09-05"
    assert analytics["sync_state"]["last_analytics_sync_at"]

    failed = collect_account_publish_metrics(
        account_id,
        platform="youtube",
        collector=FailingCollector(),
        active_limit=10,
    )
    assert failed["collected"] == 0
    assert failed["failed"] == 2
    assert failed["sync_state"]["analytics_status"] == "failed"
    assert "all 2 analytics items failed" in failed["sync_state"]["last_error"]

    print("Platform account sync-state smoke test passed")
    print("Content sync -> bounded incremental checkpoint")
    print("Full refresh -> explicit repair/reconciliation mode")
    print("Analytics batch -> success/failure checkpoint state")


if __name__ == "__main__":
    main()
