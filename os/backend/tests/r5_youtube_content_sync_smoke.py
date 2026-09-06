import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from assets.manager import get_assets
from integrations.youtube import YouTubeContentSync
from publish.manager import get_publish_tasks


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeChannels:
    def list(self, **kwargs):
        assert kwargs["mine"] is True
        return FakeRequest(
            {
                "items": [
                    {
                        "id": "channel-1",
                        "snippet": {"title": "Remote Pay Guide"},
                        "contentDetails": {
                            "relatedPlaylists": {"uploads": "uploads-1"}
                        },
                    }
                ]
            }
        )


class FakePlaylistItems:
    def list(self, **kwargs):
        assert kwargs["playlistId"] == "uploads-1"
        return FakeRequest(
            {
                "items": [
                    {
                        "contentDetails": {"videoId": "video-a"},
                        "snippet": {
                            "title": "Video A",
                            "publishedAt": "2026-09-01T00:00:00Z",
                        },
                    },
                    {
                        "contentDetails": {"videoId": "video-b"},
                        "snippet": {
                            "title": "Video B",
                            "publishedAt": "2026-09-02T00:00:00Z",
                        },
                    },
                ]
            }
        )


class FakeVideos:
    def list(self, **kwargs):
        ids = kwargs["id"].split(",")
        items = []
        for video_id in ids:
            items.append(
                {
                    "id": video_id,
                    "snippet": {
                        "title": "Video A" if video_id == "video-a" else "Video B",
                        "publishedAt": "2026-09-01T00:00:00Z",
                    },
                    "status": {
                        "privacyStatus": "public" if video_id == "video-a" else "unlisted"
                    },
                }
            )
        return FakeRequest({"items": items})


class FakeYouTubeService:
    def channels(self):
        return FakeChannels()

    def playlistItems(self):
        return FakePlaylistItems()

    def videos(self):
        return FakeVideos()


def reset_test_db():
    Path("os/database").mkdir(parents=True, exist_ok=True)
    db = Path("os/database/os.db")
    if db.exists():
        db.unlink()


def main():
    reset_test_db()
    sync = YouTubeContentSync(service=FakeYouTubeService())

    first = sync.sync(account_id=7, max_results=10)
    assert first["channel_id"] == "channel-1"
    assert first["channel_title"] == "Remote Pay Guide"
    assert first["found"] == 2
    assert first["imported"] == 2
    assert first["already_present"] == 0

    assets = get_assets()
    tasks = get_publish_tasks()
    assert len(assets) == 2
    assert len(tasks) == 2
    assert all(task["platform"] == "youtube" for task in tasks)
    assert all(task["account_id"] == 7 for task in tasks)
    assert all(task["status"] == "published" for task in tasks)
    assert {task["platform_video_id"] for task in tasks} == {"video-a", "video-b"}

    second = sync.sync(account_id=7, max_results=10)
    assert second["found"] == 2
    assert second["imported"] == 0
    assert second["already_present"] == 2
    assert len(get_publish_tasks()) == 2

    print("YouTube content sync smoke test passed")
    print("Existing uploads -> local assets + published tasks")
    print("Repeated sync -> idempotent")


if __name__ == "__main__":
    main()
