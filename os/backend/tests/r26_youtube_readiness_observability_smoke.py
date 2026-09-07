import json
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

from analytics.adapters.youtube import YouTubeAnalyticsAdapter
from analytics.backfill_runtime import AnalyticsBackfillWorker, create_operation
from data.sync_state import get_sync_state
from oauth.manager import create_token
from oauth.providers.youtube import YOUTUBE_ANALYTICS_SCOPE, YOUTUBE_READ_SCOPE
from publish.manager import create_publish_task, update_publish_status
from publish.models import PublishTask


DB_PATH = Path("os/database/os.db")
CONFIG_KEYS = (
    "YOUTUBE_OAUTH_CLIENT_ID",
    "YOUTUBE_OAUTH_CLIENT_SECRET",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
)


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
        conn.commit()


def add_account(account_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO accounts (id, platform, account_name, status) VALUES (?, 'youtube', ?, 'connected')",
            (account_id, f"account-{account_id}"),
        )
        conn.commit()


def add_published(account_id, index):
    content_id = f"content-{account_id}-{index}"
    platform_video_id = f"youtube-{account_id}-{index}"
    task = create_publish_task(
        PublishTask(
            asset_id=f"asset-{account_id}-{index}",
            video_id=content_id,
            platform="youtube",
            account_id=account_id,
            status="published",
            scheduled_time=f"2026-09-{index:02d}T00:00:00+00:00",
        )
    )
    update_publish_status(
        task["id"], "published", platform_video_id=platform_video_id
    )


class AlwaysFailCollector:
    def collect(self, *args, **kwargs):
        raise RuntimeError(
            "OAuth initialization failed; client_secret=must-not-leak "
            "access_token=also-private Authorization=Bearer-private"
        )


def main():
    reset_db()
    original = {key: os.environ.get(key) for key in CONFIG_KEYS}
    try:
        for key in CONFIG_KEYS:
            os.environ.pop(key, None)

        add_account(2600)
        create_token(
            {
                "account_id": 2600,
                "provider": "youtube",
                "access_token": "stored-access-secret",
                "refresh_token": "stored-refresh-secret",
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(hours=1)
                ).isoformat(),
                "scopes": [YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE],
            }
        )
        adapter = YouTubeAnalyticsAdapter()
        missing_config = adapter.readiness(account_id=2600)
        assert missing_config["credential_found"] is True
        assert missing_config["oauth_client_configured"] is False
        assert missing_config["credential_ready"] is False
        assert missing_config["ready"] is False
        assert "configuration is unavailable" in missing_config["reason"]

        create_token(
            {
                "account_id": 2600,
                "provider": "youtube",
                "access_token": "expired-access-secret",
                "refresh_token": "stored-refresh-secret",
                "expires_at": (
                    datetime.now(timezone.utc) - timedelta(minutes=1)
                ).isoformat(),
                "scopes": [YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE],
            }
        )
        expired = adapter.readiness(account_id=2600)
        assert expired["token_expired"] is True
        assert expired["refresh_required"] is True
        assert expired["refresh_token_found"] is True
        assert expired["refresh_ready"] is False
        assert expired["ready"] is False

        os.environ["YOUTUBE_OAUTH_CLIENT_ID"] = "runtime-client-id"
        os.environ["YOUTUBE_OAUTH_CLIENT_SECRET"] = "runtime-client-secret"
        configured = adapter.readiness(account_id=2600)
        assert configured["oauth_client_configured"] is True
        assert configured["refresh_ready"] is True
        assert configured["credential_ready"] is True
        assert configured["ready"] is True
        serialized = json.dumps(configured)
        assert "runtime-client-secret" not in serialized
        assert "stored-access-secret" not in serialized
        assert "stored-refresh-secret" not in serialized

        # Ten request failures retain a useful first root cause while all
        # credential-shaped values are redacted in state and operation output.
        for index in range(1, 11):
            add_published(2600, index)
        operation = create_operation(
            2600,
            platform="youtube",
            date_range="custom",
            start_date="2026-09-06",
            end_date="2026-09-06",
        )
        result = AnalyticsBackfillWorker(
            batch_size=10,
            collector=AlwaysFailCollector(),
            clock=lambda: datetime(2026, 9, 7, tzinfo=timezone.utc),
        ).process_once()
        assert result["operation_id"] == operation["operation_id"]
        assert result["status"] == "failed"
        assert result["failed_work"] == 10
        assert "10 backfill request(s) failed" in result["last_error"]
        assert "OAuth initialization failed" in result["last_error"]
        assert "must-not-leak" not in result["last_error"]
        assert "also-private" not in result["last_error"]
        assert "Bearer-private" not in result["last_error"]
        assert result["last_error"].count("[redacted]") == 3
        state_error = get_sync_state(2600, "youtube")["backfill_error"]
        assert state_error == result["last_error"]
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    print("YouTube OAuth readiness and backfill observability smoke test passed")
    print("runtime config; expiry/refresh; safe contract; ten-failure root cause redaction")


if __name__ == "__main__":
    main()
