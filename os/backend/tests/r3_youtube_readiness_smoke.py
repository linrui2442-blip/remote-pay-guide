import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from accounts.manager import create_account
from accounts.models import Account
from assets.manager import create_video_asset
from oauth.manager import consume_oauth_state, create_oauth_state
from oauth.providers.youtube import (
    YouTubeOAuthConfigurationError,
    YouTubeOAuthProvider,
)
from publish.asset_resolver import AssetResolver
from publish.manager import create_publish_task, get_publish_task
from publish.models import PublishTask
from publish.queue import PublishQueue
from publish.worker import PublishWorker


R2_SAFE_ASSET_URL = (
    "https://linrui2442-blip.github.io/remote-pay-guide/"
    "media/task1-asset_d7bdb5eb.mp4"
)


def reset_test_db():
    Path("os/database").mkdir(parents=True, exist_ok=True)
    db = Path("os/database/os.db")
    if db.exists():
        db.unlink()


def test_publish_task_schema():
    task = PublishTask(
        asset_id="asset_schema_test",
        platform="youtube",
        account_id=1,
        title="Remote Pay Guide OS Publishing Bridge Test",
        description="Automated private integration test.",
        tags=["remote-pay-guide", "integration-test"],
        privacy_status="private",
    )
    stored = create_publish_task(task)
    assert stored["asset_id"] == "asset_schema_test"
    assert stored["privacy_status"] == "private"
    assert stored["tags"] == ["remote-pay-guide", "integration-test"]


def test_r2_online_asset_to_temp_and_cleanup():
    resolver = AssetResolver(max_bytes=10 * 1024 * 1024)
    prepared = resolver.prepare(
        {
            "asset_id": "asset_r2_safe_test",
            "asset_url": R2_SAFE_ASSET_URL,
            "file_path": None,
            "location": R2_SAFE_ASSET_URL,
        }
    )
    path = Path(prepared.file_path)
    assert prepared.temporary is True
    assert path.is_file()
    assert path.stat().st_size > 0
    prepared.cleanup()
    assert not path.exists()


def test_invalid_asset_id_failure():
    queue = PublishQueue()
    task = create_publish_task(
        PublishTask(
            asset_id="asset_does_not_exist",
            platform="youtube",
            account_id=999999,
            title="should not publish",
            privacy_status="private",
        )
    )
    queue.add_task(task["id"])
    PublishWorker(queue).run_once()
    failed = get_publish_task(task["id"])
    assert failed["status"] == "failed"
    assert "video asset not found" in (failed["error_message"] or "")


def test_uncredentialed_account_failure_without_upload():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
        handle.write(b"local-resolution-only")
        local_path = handle.name

    try:
        asset = create_video_asset(
            {
                "asset_id": "asset_no_oauth_test",
                "video_id": "r3-no-oauth",
                "source_provider": "external",
                "storage_type": "external",
                "asset_url": None,
                "file_path": local_path,
                "status": "ready",
                "metadata": {},
                "source": "external",
                "location": local_path,
            }
        )
        account = create_account(
            Account(platform="youtube", account_name="r3-test-no-oauth")
        )
        queue = PublishQueue()
        task = create_publish_task(
            PublishTask(
                asset_id=asset.asset_id,
                platform="youtube",
                account_id=account["id"],
                title="Remote Pay Guide OS Publishing Bridge Test",
                description="Automated private integration test.",
                privacy_status="private",
            )
        )
        queue.add_task(task["id"])
        PublishWorker(queue).run_once()
        failed = get_publish_task(task["id"])
        assert failed["status"] == "failed"
        assert "OAuth credential not found" in (failed["error_message"] or "")
    finally:
        try:
            os.remove(local_path)
        except FileNotFoundError:
            pass


def test_oauth_state_is_single_use():
    state = "r3-test-state"
    create_oauth_state(42, state)
    assert consume_oauth_state(42, state) is True
    assert consume_oauth_state(42, state) is False


def test_oauth_provider_is_not_mocked():
    source = (BACKEND / "oauth" / "providers" / "youtube.py").read_text(
        encoding="utf-8"
    )
    assert "mock_access_token" not in source
    assert "mock_refresh_token" not in source
    provider = YouTubeOAuthProvider(
        client_id=None,
        client_secret=None,
        redirect_uri=None,
    )
    if not (
        os.getenv("YOUTUBE_OAUTH_CLIENT_ID")
        and os.getenv("YOUTUBE_OAUTH_CLIENT_SECRET")
        and os.getenv("YOUTUBE_OAUTH_REDIRECT_URI")
    ):
        try:
            provider.get_authorization_url()
        except YouTubeOAuthConfigurationError:
            pass
        else:
            raise AssertionError("OAuth provider must not invent credentials")


def test_no_postiz_import_in_os_publish_path():
    publish_root = BACKEND / "publish"
    for path in publish_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "postiz" not in text, f"Postiz reference found in {path}"
        assert "postiz_api_base_url" not in text, f"Postiz env reference found in {path}"


def main():
    reset_test_db()
    test_publish_task_schema()
    test_r2_online_asset_to_temp_and_cleanup()
    test_invalid_asset_id_failure()
    test_uncredentialed_account_failure_without_upload()
    test_oauth_state_is_single_use()
    test_oauth_provider_is_not_mocked()
    test_no_postiz_import_in_os_publish_path()
    print("R3 readiness smoke tests passed")
    print("R2 asset URL downloaded in runner temp storage and cleaned")
    print("Invalid asset_id -> failed")
    print("Missing OAuth credential -> failed")
    print("OAuth state -> single-use")
    print("YouTube OAuth provider -> real implementation, no mock tokens")
    print("OS publish path Postiz references -> none")


if __name__ == "__main__":
    main()
