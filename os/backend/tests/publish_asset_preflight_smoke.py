from test_database_helper import TEST_DATABASE_PATH, assert_safe_test_database_path
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from accounts.manager import create_account
from accounts.models import Account
from assets.manager import create_video_asset
from publish.models import PublishTask
from publish.orchestrator import PublishContractError, prepare_publish_task
from publish.registry import platform_registry, register_adapter


class PreflightAdapter:
    platform_name = "asset-preflight-test"

    def __init__(self):
        self.status = "initialized"

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


def expect_contract_error(callback, text):
    try:
        callback()
    except PublishContractError as exc:
        assert text in str(exc), str(exc)
        return
    raise AssertionError(f"expected PublishContractError containing: {text}")


def prepare(asset_id, account_id):
    return prepare_publish_task(
        PublishTask(
            asset_id=asset_id,
            platform="asset-preflight-test",
            account_id=account_id,
            privacy_status="private",
        )
    )


def main():
    assert_safe_test_database_path(TEST_DATABASE_PATH)
    register_adapter("asset-preflight-test", PreflightAdapter(), replace=True)
    account = create_account(
        Account(platform="asset-preflight-test", account_name="Asset Preflight")
    )

    try:
        # A stale local path must not mask a valid remote fallback. This is a
        # prepare-only check: no HTTP request and no upload is made here.
        create_video_asset(
            {
                "asset_id": "asset-stale-local-with-url",
                "video_id": "stale-local-with-url",
                "source_provider": "github",
                "storage_type": "github_pages",
                "asset_url": "https://example.test/video.mp4",
                "file_path": str(ROOT / "missing" / "video.mp4"),
                "status": "ready",
                "metadata": {},
                "source": "github",
                "location": "https://example.test/video.mp4",
            }
        )
        prepared = prepare("asset-stale-local-with-url", account["id"])
        assert prepared["created"] is True
        assert prepared["task"]["status"] == "pending"

        # Arbitrary registry locations are not upload sources. They must fail at
        # prepare time instead of creating a pending task that can only fail in
        # the worker later.
        create_video_asset(
            {
                "asset_id": "asset-non-url-location",
                "video_id": "non-url-location",
                "source_provider": "external",
                "storage_type": "external",
                "status": "ready",
                "metadata": {},
                "source": "external",
                "location": "artifact-key-without-download-url",
            }
        )
        expect_contract_error(
            lambda: prepare("asset-non-url-location", account["id"]),
            "no usable file_path or http/https asset_url",
        )

        # If an explicit asset_url is present, it must match the resolver's
        # supported http/https contract. A different scheme cannot be rescued by
        # a second location value because AssetResolver would use asset_url first.
        create_video_asset(
            {
                "asset_id": "asset-invalid-url-scheme",
                "video_id": "invalid-url-scheme",
                "source_provider": "external",
                "storage_type": "external",
                "asset_url": "ftp://example.test/video.mp4",
                "status": "ready",
                "metadata": {},
                "source": "external",
                "location": "https://example.test/fallback.mp4",
            }
        )
        expect_contract_error(
            lambda: prepare("asset-invalid-url-scheme", account["id"]),
            "no usable file_path or http/https asset_url",
        )
    finally:
        platform_registry.pop("asset-preflight-test", None)

    print("Publish asset preflight smoke test passed")
    print("stale local path + valid remote URL -> pending without network")
    print("non-URL location -> blocked before task persistence")
    print("unsupported asset_url scheme -> blocked before task persistence")


if __name__ == "__main__":
    main()
