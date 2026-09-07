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
from publish.manager import get_publish_task
from publish.models import PublishTask
from publish.orchestrator import (
    PublishContractError,
    execute_publish_task,
    get_publish_execution_readiness,
    prepare_publish_task,
)
from publish.registry import platform_registry, register_adapter


def reset_test_db():
    Path("os/database").mkdir(parents=True, exist_ok=True)
    db = Path("os/database/os.db")
    if db.exists():
        db.unlink()


class R20LiveAdapter:
    platform_name = "r20-test"

    def __init__(self):
        self.status = "initialized"
        self.publish_count = 0

    def initialize(self):
        self.status = "ready"
        return self.get_status()

    def get_status(self):
        return {
            "platform": self.platform_name,
            "status": self.status,
            "execution_mode": "live_test",
            "publish_ready": self.status == "ready",
        }

    def publish_video(self, video_asset, account_id=None):
        assert video_asset["asset_id"] == "asset-r20"
        assert account_id is not None
        self.publish_count += 1
        return {
            "platform": self.platform_name,
            "status": "published",
            "video_id": "r20-platform-video",
            "url": "https://example.test/r20-platform-video",
        }


def expect_contract_error(callback, text):
    try:
        callback()
    except PublishContractError as exc:
        assert text in str(exc), str(exc)
        return
    raise AssertionError(f"expected PublishContractError containing: {text}")


def main():
    reset_test_db()

    # Built-in registry truthfulness: only YouTube is a live OS publish adapter.
    youtube = get_publish_execution_readiness("youtube")
    assert youtube["publish_ready"] is True
    assert youtube["execution_mode"] == "live_api"
    for platform in ("facebook", "instagram", "tiktok"):
        readiness = get_publish_execution_readiness(platform)
        assert readiness["adapter_registered"] is True
        assert readiness["publish_ready"] is False
        assert readiness["execution_mode"] == "simulated"

    fake = R20LiveAdapter()
    register_adapter("r20-test", fake, replace=True)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
        handle.write(b"r20-publish-center-contract")
        local_path = handle.name

    try:
        asset = create_video_asset(
            {
                "asset_id": "asset-r20",
                "video_id": "content-r20",
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
            Account(platform="r20-test", account_name="R20 Publish Account")
        )

        draft = PublishTask(
            asset_id=asset.asset_id,
            video_id=asset.video_id,
            platform="r20-test",
            account_id=account["id"],
            title="R20 Publish Center Contract",
            description="No external network call is made by this smoke test.",
            privacy_status="private",
        )

        prepared = prepare_publish_task(draft)
        assert prepared["created"] is True
        task_id = prepared["task"]["id"]
        assert prepared["task"]["status"] == "pending"
        assert fake.publish_count == 0, "preparing a task must never publish"

        duplicate = prepare_publish_task(draft)
        assert duplicate["created"] is False
        assert duplicate["task"]["id"] == task_id
        assert fake.publish_count == 0

        wrong_account = create_account(
            Account(platform="wrong-platform", account_name="Wrong Platform")
        )
        expect_contract_error(
            lambda: prepare_publish_task(
                PublishTask(
                    asset_id=asset.asset_id,
                    platform="r20-test",
                    account_id=wrong_account["id"],
                )
            ),
            "is bound to wrong-platform, not r20-test",
        )

        facebook_account = create_account(
            Account(platform="facebook", account_name="Placeholder Facebook")
        )
        expect_contract_error(
            lambda: prepare_publish_task(
                PublishTask(
                    asset_id=asset.asset_id,
                    platform="facebook",
                    account_id=facebook_account["id"],
                )
            ),
            "Facebook live OS publishing adapter is not configured",
        )

        executed = execute_publish_task(task_id)
        assert executed["executed"] is True
        assert executed["worker"]["processed"] == 1
        assert executed["task"]["status"] == "published"
        assert executed["task"]["platform_video_id"] == "r20-platform-video"
        assert executed["task"]["published_url"] == "https://example.test/r20-platform-video"
        assert fake.publish_count == 1

        persisted = get_publish_task(task_id)
        assert persisted["status"] == "published"

        expect_contract_error(
            lambda: execute_publish_task(task_id),
            "cannot be executed",
        )
        assert fake.publish_count == 1, "published tasks must not execute twice"
    finally:
        platform_registry.pop("r20-test", None)
        try:
            os.remove(local_path)
        except FileNotFoundError:
            pass

    print("R20 Publish Center execution contract smoke test passed")
    print("prepare -> idempotent pending task; no upload")
    print("simulated adapters -> blocked before execution")
    print("explicit execute -> one worker publish -> persisted published result")
    print("published task -> duplicate execution blocked")


if __name__ == "__main__":
    main()
