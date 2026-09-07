import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)
os.environ.setdefault("YOUTUBE_OAUTH_CLIENT_ID", "account-analytics-test-client")
os.environ.setdefault("YOUTUBE_OAUTH_CLIENT_SECRET", "account-analytics-test-secret")

from analytics.account_manager import get_latest_account_metrics
from analytics.collector import AnalyticsCollector
from analytics.publish_bridge import collect_account_publish_metrics
from analytics.youtube_api import YouTubeAnalyticsAPIClient
from oauth.manager import create_token
from oauth.providers.youtube import YOUTUBE_ANALYTICS_SCOPE, YOUTUBE_READ_SCOPE


class FakeYouTubeAnalyticsClient:
    def initialize(self, credentials=None):
        assert credentials is not None
        return {"platform": "youtube", "status": "ready"}

    def collect_channel_metrics(self, start_date=None, end_date=None):
        assert start_date == "2026-08-09"
        assert end_date == "2026-09-05"
        return {
            "views": 900,
            "watch_time": 5400,
            "average_view_duration": 21.5,
            "retention": 64.2,
            "likes": 44,
            "comments": 8,
            "shares": 7,
            "subscribers_gained": 12,
            "subscribers_lost": 2,
            "start_date": start_date,
            "end_date": end_date,
        }


class BatchCollector:
    def collect_account(self, platform, account_id=None, **kwargs):
        return {
            "account_id": account_id,
            "platform": platform,
            "period_end": kwargs.get("end_date") or "2026-09-05",
            "metrics": {"views": 900},
        }

    def collect(self, *args, **kwargs):
        raise AssertionError("no content tasks should be present in this test")


def reset_test_db():
    Path("os/database").mkdir(parents=True, exist_ok=True)
    db = Path("os/database/os.db")
    if db.exists():
        db.unlink()


def main():
    reset_test_db()
    account_id = 1300
    create_token(
        {
            "account_id": account_id,
            "provider": "youtube",
            "access_token": "account-analytics-access",
            "scopes": [YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE],
        }
    )

    collector = AnalyticsCollector(
        youtube_client_factory=FakeYouTubeAnalyticsClient
    )
    saved = collector.collect_account(
        "youtube",
        account_id=account_id,
        start_date="2026-08-09",
        end_date="2026-09-05",
    )
    assert saved["account_id"] == account_id
    assert saved["platform"] == "youtube"
    assert saved["period_start"] == "2026-08-09"
    assert saved["period_end"] == "2026-09-05"
    assert saved["metrics"]["views"] == 900
    assert saved["metrics"]["average_view_percentage"] == 64.2
    assert saved["metrics"]["subscribers_gained"] == 12
    assert saved["metrics"]["subscribers_lost"] == 2

    latest = get_latest_account_metrics(account_id, platform="youtube")
    assert len(latest) == 1
    assert latest[0]["metrics"]["watch_time"] == 5400

    normalized = YouTubeAnalyticsAPIClient.normalize_channel_response(
        {
            "columnHeaders": [
                {"name": "views"},
                {"name": "estimatedMinutesWatched"},
                {"name": "averageViewDuration"},
                {"name": "averageViewPercentage"},
                {"name": "likes"},
                {"name": "comments"},
                {"name": "shares"},
                {"name": "subscribersGained"},
                {"name": "subscribersLost"},
            ],
            "rows": [[100, 10, 20, 50, 5, 2, 1, 3, 1]],
        }
    )
    assert normalized["watch_time"] == 600
    assert normalized["subscribers_gained"] == 3
    assert normalized["subscribers_lost"] == 1

    batch = collect_account_publish_metrics(
        account_id,
        platform="youtube",
        collector=BatchCollector(),
        start_date="2026-08-09",
        end_date="2026-09-05",
    )
    assert batch["found"] == 0
    assert batch["collected"] == 0
    assert batch["account_metric"]["metrics"]["views"] == 900
    assert batch["analytics_cursor"] == "2026-09-05"
    assert batch["sync_state"]["analytics_status"] == "success"

    print("Account analytics smoke test passed")
    print("YouTube channel Analytics -> account snapshot storage")
    print("Account batch sync -> account + active-content architecture")


if __name__ == "__main__":
    main()
