import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from assets.manager import get_assets
from config.network import save_proxy_settings
from data.growth import get_content_funnel
from integrations.google_transport import build_authorized_session
from integrations.youtube import YouTubeContentSync
from intelligence.feedback import analyze_feedback
from intelligence.strategy import build_production_strategy
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


class FakeCommentThreads:
    def list(self, **kwargs):
        video_id = kwargs["videoId"]
        if video_id == "video-b":
            return FakeRequest({"items": []})
        return FakeRequest(
            {
                "items": [
                    {
                        "id": "thread-1",
                        "snippet": {
                            "totalReplyCount": 0,
                            "topLevelComment": {
                                "id": "comment-1",
                                "snippet": {
                                    "textOriginal": "Please make a video explaining how to choose a USDT address for a customer.",
                                    "likeCount": 2,
                                    "publishedAt": "2026-09-06T12:00:00Z",
                                    "updatedAt": "2026-09-06T12:00:00Z",
                                },
                            },
                        },
                    }
                ]
            }
        )


class FakeYouTubeService:
    def channels(self):
        return FakeChannels()

    def playlistItems(self):
        return FakePlaylistItems()

    def videos(self):
        return FakeVideos()

    def commentThreads(self):
        return FakeCommentThreads()


class FakeAuthorizedSession:
    def __init__(self, credentials):
        self.credentials = credentials
        self.proxies = {}


def reset_test_db():
    Path("os/database").mkdir(parents=True, exist_ok=True)
    db = Path("os/database/os.db")
    if db.exists():
        db.unlink()


def verify_manual_proxy_transport():
    reset_test_db()
    save_proxy_settings("manual", "http://127.0.0.1:7897")
    session = build_authorized_session(
        object(),
        session_factory=FakeAuthorizedSession,
    )
    assert session.proxies == {
        "http": "http://127.0.0.1:7897",
        "https": "http://127.0.0.1:7897",
    }
    save_proxy_settings("disabled")


def main():
    verify_manual_proxy_transport()
    reset_test_db()
    sync = YouTubeContentSync(service=FakeYouTubeService())

    first = sync.sync(account_id=7, max_results=10, max_comments_per_video=20)
    assert first["channel_id"] == "channel-1"
    assert first["channel_title"] == "Remote Pay Guide"
    assert first["found"] == 2
    assert first["imported"] == 2
    assert first["already_present"] == 0
    assert first["feedback_found"] == 1
    assert first["feedback_imported"] == 1
    assert first["feedback_already_present"] == 0

    assets = get_assets()
    tasks = get_publish_tasks()
    assert len(assets) == 2
    assert len(tasks) == 2
    assert all(task["platform"] == "youtube" for task in tasks)
    assert all(task["account_id"] == 7 for task in tasks)
    assert all(task["status"] == "published" for task in tasks)
    assert {task["platform_video_id"] for task in tasks} == {"video-a", "video-b"}

    funnel = get_content_funnel("video-a")
    assert funnel["intent"]["by_type"]["content_feedback"] == 1
    assert "USDT address" in funnel["intent"]["recent_feedback"][0]["text"]

    feedback = analyze_feedback(
        {"video_id": "video-a", "performance": {}, "funnel": funnel}
    )
    assert feedback.audience_feedback
    strategy = build_production_strategy(feedback)
    assert strategy.parameters["strategy_type"] == "respond_to_audience_feedback"
    assert "USDT address" in strategy.topic_direction

    second = sync.sync(account_id=7, max_results=10, max_comments_per_video=20)
    assert second["found"] == 2
    assert second["imported"] == 0
    assert second["already_present"] == 2
    assert second["feedback_found"] == 1
    assert second["feedback_imported"] == 0
    assert second["feedback_already_present"] == 1
    assert len(get_publish_tasks()) == 2

    print("YouTube content sync smoke test passed")
    print("Manual OS proxy -> explicit Google requests transport")
    print("Existing uploads -> local external assets + published tasks")
    print("YouTube comments -> Data Center audience feedback")
    print("Audience feedback -> next-topic strategy signal")
    print("Repeated sync -> idempotent")


if __name__ == "__main__":
    main()
