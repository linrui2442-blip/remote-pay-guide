"""Isolated full-chain verification for the GitHub Production Line 1 path."""
import os
import sys
import tempfile
from pathlib import Path

DB = Path(tempfile.gettempdir()) / "remote-pay-guide-p1-r46.db"
DB.unlink(missing_ok=True)
os.environ["OS_TESTING"] = "1"
os.environ["OS_DATABASE_PATH"] = str(DB)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assets.manager import get_asset_by_asset_id
from production.providers.github import GitHubProductionProvider
from production.providers import github_completion
from production.results.manager import create_result, get_results
from production.runtime.worker import ProductionRuntimeWorker
from production.tasks.manager import create_task
from production.tasks.models import ProductionTask
from production.tasks.scheduler import schedule_task


PUBLIC_URL = "https://example.invalid/media/short12.mp4"


class FakeClient:
    owner = "example"
    repo = "remote-pay-guide"

    def trigger_workflow(self, workflow, branch="main", inputs=None):
        return {"workflow": workflow, "branch": branch, "inputs": inputs or {}}


class SuccessMonitor:
    def snapshot_run_ids(self, *_): return set()
    def discover_run(self, *_args, **_kwargs): return {"id": 1200, "status": "queued", "conclusion": None}
    def wait_for_terminal(self, *_args, **_kwargs): return {"id": 1200, "status": "completed", "conclusion": "success", "html_url": "https://example.invalid/run/1200"}
    def discover_artifact(self, *_args, **_kwargs): return {"id": 77, "name": "remote-pay-guide-short12", "size_in_bytes": 10, "archive_download_url": "https://example.invalid/artifact"}


class FailureMonitor(SuccessMonitor):
    def __init__(self, mode): self.mode = mode
    def wait_for_terminal(self, *_args, **_kwargs):
        if self.mode == "render": return {"id": 1201, "status": "completed", "conclusion": "failure"}
        return super().wait_for_terminal(*_args, **_kwargs)
    def discover_artifact(self, *_args, **_kwargs):
        if self.mode == "artifact": raise RuntimeError("Expected artifact was not found")
        return super().discover_artifact(*_args, **_kwargs)


def fake_promotion(**_kwargs):
    if fake_promotion.mode == "failure": raise RuntimeError("promotion failed")
    return {"storage_type": "github_pages", "asset_url": PUBLIC_URL, "asset_ready": True, "asset_filename": "short12.mp4"}


fake_promotion.mode = "success"


def run_success():
    client = FakeClient()
    provider = GitHubProductionProvider(client=client)
    provider.monitor = SuccessMonitor()
    task = create_task(ProductionTask(source="ai_intelligence", objective="r46", provider="github", parameters={
        "task_file": "tasks-short12.jsonl", "content_id": "short12", "hook": "Check the network.",
        "artifact_name": "remote-pay-guide-short12", "asset_filename": "short12.mp4",
    }, workflow="render-short01.yml", branch="main"))
    job = schedule_task(task)
    # Use the real worker/provider/completion/result/binding path, with only transport fakes.
    import production.runtime.worker as worker_module
    worker_module.get_provider = lambda name: provider
    github_completion.GitHubRunMonitor = lambda _client: SuccessMonitor()
    github_completion.promote_artifact_to_pages = fake_promotion
    result = ProductionRuntimeWorker().run(job)
    pr = result["production_result"]
    assert result["status"] == pr["status"] == "completed", result
    assert pr["video_id"] == "short12"
    assert pr["output"]["content_id"] == "short12"
    assert pr["output"]["storage_type"] == "github_pages"
    assert pr["output"]["asset_url"] == PUBLIC_URL
    assert pr["output"]["asset_ready"] is True
    asset = get_asset_by_asset_id(pr["asset_id"])
    assert asset["video_id"] == "short12"
    assert asset["source_provider"] == "github"
    assert asset["storage_type"] == "github_pages"
    assert asset["status"] == "ready"
    assert len([x for x in get_results() if x["runtime_job_id"] == job["id"]]) == 1
    # Rebinding an already-completed result is not done by the worker and cannot create a second result.
    assert len(get_results()) == 1
    return pr


def run_failure(mode):
    client = FakeClient()
    result = create_result({"runtime_job_id": 3000 + len(get_results()), "provider": "github", "status": "submitted",
                            "video_id": "short12", "output": {"github_run_id": 1201}})
    github_completion.GitHubRunMonitor = lambda _client: FailureMonitor(mode)
    github_completion.promote_artifact_to_pages = fake_promotion
    fake_promotion.mode = "failure" if mode == "promotion" else "success"
    completed = github_completion.complete_github_execution(result["id"], {"task_id": None}, client=client)
    assert completed["status"] == "failed"
    fake_promotion.mode = "success"


run_success()
run_failure("render")
run_failure("artifact")
run_failure("promotion")
print("P1 GitHub Line 1 full-chain smoke passed")
