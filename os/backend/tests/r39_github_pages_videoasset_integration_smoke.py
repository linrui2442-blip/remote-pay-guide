"""Network-free contract for GitHub Pages production results and publish prepare."""

from assets.manager import get_asset_by_asset_id
from production.results.manager import create_result
from production.runtime.worker import ProductionRuntimeWorker
from publish.models import PublishTask
import publish.orchestrator as orchestrator


PUBLIC_URL = "https://linrui2442-blip.github.io/remote-pay-guide/media/test-video.mp4"


def test_github_result_binds_ready_video_asset_and_instagram_prepare(monkeypatch):
    # create_result is the same completion boundary used by the runtime worker;
    # no GitHub or Meta transport is involved in this contract test.
    result = create_result(
        {
            "runtime_job_id": 901,
            "provider": "github",
            "status": "completed",
            "output": {
                "video_id": "content-test-video",
                "storage_type": "github_pages",
                "asset_url": PUBLIC_URL,
                "asset_ready": True,
                "location": PUBLIC_URL,
            },
        }
    )
    assert result["status"] == "completed"
    assert result["video_id"] == "content-test-video"
    assert result["asset_id"]
    assert result["asset_status"] == "ready"

    asset = get_asset_by_asset_id(result["asset_id"])
    assert asset
    assert asset["video_id"] == "content-test-video"
    assert asset["source_provider"] == "github"
    assert asset["storage_type"] == "github_pages"
    assert asset["status"] == "ready"
    assert asset["asset_url"] == PUBLIC_URL
    assert asset["location"] == PUBLIC_URL

    monkeypatch.setattr(
        orchestrator,
        "get_publish_execution_readiness",
        lambda platform: {"platform": platform, "publish_ready": True},
    )
    monkeypatch.setattr(
        orchestrator,
        "get_publish_account_readiness",
        lambda platform, account_id: {"ready": True},
    )
    monkeypatch.setattr(
        orchestrator,
        "get_account",
        lambda account_id: {"id": account_id, "platform": "instagram"},
    )

    prepared = orchestrator.prepare_publish_task(
        PublishTask(
            asset_id=result["asset_id"],
            video_id="content-test-video",
            platform="instagram",
            account_id=3,
            status="pending",
        )
    )
    assert prepared["created"] is True
    assert prepared["task"]["status"] == "pending"
    assert prepared["task"]["asset_id"] == result["asset_id"]
    assert prepared["task"]["video_id"] == "content-test-video"
    assert prepared["asset_id"] == result["asset_id"]


def test_runtime_worker_preserves_provider_content_identity(monkeypatch):
    class Provider:
        def run(self, job):
            return {
                "status": "completed",
                "provider": "github",
                "output": {"content_id": "provider-content-1", "asset_url": PUBLIC_URL},
            }

    monkeypatch.setattr("production.runtime.worker.get_provider", lambda _: Provider())
    monkeypatch.setattr("production.runtime.worker.update_job_status", lambda *args: None)
    monkeypatch.setattr("production.runtime.worker.update_job_result", lambda *args: None)
    monkeypatch.setattr("production.runtime.worker.get_task", lambda _: None)

    result = ProductionRuntimeWorker().run({"id": 902, "task_id": 999, "provider": "github"})
    production_result = result["production_result"]
    assert production_result["status"] == "completed"
    assert production_result["video_id"] == "provider-content-1"


def test_public_url_verifier_rejects_html_and_accepts_video(monkeypatch):
    from assets import github_pages

    class Response:
        def __init__(self, status, content_type, length="12", url=PUBLIC_URL):
            self.status_code = status
            self.headers = {"Content-Type": content_type, "Content-Length": length}
            self.url = url

        def close(self):
            pass

    class Session:
        def __init__(self, response):
            self.response = response

        def head(self, *args, **kwargs):
            return self.response

    assert github_pages._verify_public_url(
        PUBLIC_URL, max_attempts=1, poll_interval=0,
        session=Session(Response(200, "video/mp4")),
    ) is True
    try:
        github_pages._verify_public_url(
            PUBLIC_URL, max_attempts=1, poll_interval=0,
            session=Session(Response(200, "text/html")),
        )
    except TimeoutError:
        pass
    else:
        raise AssertionError("HTML response must not be promoted as a video asset")
