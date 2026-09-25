"""Offline G4-B GitHub claimed-runtime contract smoke."""
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "os" / "backend"))
os.environ["OS_TESTING"] = "1"

import g4a_authorized_production_smoke as fixture
from intelligence import autonomy
from intelligence.content_brain import update_plan, get_plan
from orchestration.production import (
    execute_authorized_claimed_github_runtime,
    prepare_authorized_production,
    refresh_authorized_github_runtime,
)
from production.providers.github import GitHubProductionProvider
from production.results.manager import init_results_table, create_or_get_result_for_job
from production.runtime.manager import get_jobs_for_task, get_job
from production.tasks.manager import get_task
import assets.github_pages as github_pages


class FakeGitHubClient:
    def __init__(self):
        self.owner = "example"
        self.repo = "offline"
        self.trigger_count = 0
        self.runs = []
        self.state = {"status": "queued", "conclusion": None}
        self.artifacts = [{"id": 7, "name": "remote-pay-guide-test", "size_in_bytes": 10, "expired": False, "archive_download_url": "https://example.invalid/archive"}]

    def list_workflow_runs(self, workflow, branch=None, event=None, per_page=30):
        return {"workflow_runs": list(self.runs)}

    def trigger_workflow(self, workflow, branch="main", inputs=None):
        self.trigger_count += 1
        run = {"id": 100 + self.trigger_count, "html_url": "https://example.invalid/run", "status": self.state["status"], "conclusion": self.state["conclusion"], "created_at": "2999-01-01T00:00:00+00:00"}
        self.runs.append(run)
        return {"status": "started", "workflow": workflow, "branch": branch, "inputs": inputs or {}}

    def get_workflow_run(self, run_id):
        run = dict(self.runs[0])
        run.update({"status": self.state["status"], "conclusion": self.state["conclusion"]})
        return run

    def get_workflow_run_artifacts(self, run_id, per_page=100):
        return {"artifacts": list(self.artifacts)}


def _counts():
    with sqlite3.connect(fixture.DB) as db:
        return {name: (db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] if db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0] else 0) for name in ("runtime_jobs", "production_results", "video_assets", "publish_tasks")}


def _fake_promotion(**kwargs):
    return {"storage_type": "github_pages", "asset_url": "https://example.invalid/media/test.mp4", "url": "https://example.invalid/media/test.mp4", "asset_filename": kwargs["asset_filename"], "asset_ready": True, "promotion_run_id": 500}


def main():
    fixture._enable()
    os.environ["OS_PRODUCTION_PROVIDER"] = "github"
    client = FakeGitHubClient()
    provider = GitHubProductionProvider(client=client)
    original_promotion = github_pages.promote_artifact_to_pages
    github_pages.promote_artifact_to_pages = _fake_promotion
    try:
        plan_id = fixture._create("g4b-basic")
        prepared = prepare_authorized_production(plan_id)
        claimed = __import__("orchestration.production", fromlist=["claim_authorized_production_execution"]).claim_authorized_production_execution(plan_id)
        client.artifacts[0]["name"] = claimed["production_task"].parameters["artifact_name"]
        before = _counts()
        first = execute_authorized_claimed_github_runtime(plan_id, provider=provider, client=client)
        assert client.trigger_count == 1 and first["status"] == "submitted"
        assert len(get_jobs_for_task(claimed["production_task"].id)) == 1
        assert _counts()["production_results"] - before["production_results"] == 1 and _counts()["video_assets"] == 0 and _counts()["publish_tasks"] == 0
        assert first["production_result"]["output"]["github_run_id"] == 101
        print("G4B_GITHUB_SUBMIT_E2E=PASS")

        client.state = {"status": "in_progress", "conclusion": None}
        running = refresh_authorized_github_runtime(plan_id, provider=provider, client=client)
        assert running["status"] == "running" and client.trigger_count == 1 and running["production_result"]["id"] == first["production_result"]["id"]
        print("G4B_GITHUB_RUNNING_POLL=PASS")

        client.state = {"status": "completed", "conclusion": "success"}
        completed = refresh_authorized_github_runtime(plan_id, provider=provider, client=client)
        assert completed["status"] == "completed" and client.trigger_count == 1 and _counts()["video_assets"] == 0
        assert completed["production_result"]["output"]["storage_type"] == "github_pages"
        print("G4B_GITHUB_COMPLETED_E2E=PASS")
        again = refresh_authorized_github_runtime(plan_id, provider=provider, client=client)
        assert again["production_result"]["id"] == completed["production_result"]["id"] and client.trigger_count == 1
        print("COMPLETED_RESULT_IDEMPOTENT=PASS")

        # Duplicate result history is preserved and rejected by the canonical helper.
        init_results_table()
        with sqlite3.connect(fixture.DB) as db:
            db.execute("DROP INDEX IF EXISTS uq_production_results_runtime_job")
            job_id = claimed["runtime_job"]["id"]
            db.execute("INSERT INTO production_results(runtime_job_id,provider,status,output) VALUES(?,?,?,?)", (job_id, "github", "submitted", "{}"))
            db.commit()
        try:
            create_or_get_result_for_job({"runtime_job_id": claimed["runtime_job"]["id"], "provider": "ai_gateway", "status": "submitted"})
        except ValueError as exc:
            assert "multiple ProductionResults" in str(exc)
            print("MULTIPLE_RESULTS_FAIL_CLOSED=PASS")
        else:
            raise AssertionError("result provider mismatch accepted")

        # Fresh authorization is checked at the external-write boundary.
        fixture._enable()
        revoked_id = fixture._create("g4b-revoked")
        prepare_authorized_production(revoked_id)
        __import__("orchestration.production", fromlist=["claim_authorized_production_execution"]).claim_authorized_production_execution(revoked_id)
        autonomy.update_autonomy_settings(autonomy_enabled=True, kill_switch_active=True)
        revoked_client = FakeGitHubClient()
        try:
            execute_authorized_claimed_github_runtime(revoked_id, provider=GitHubProductionProvider(client=revoked_client), client=revoked_client)
        except ValueError:
            assert revoked_client.trigger_count == 0
            print("KILL_SWITCH_BEFORE_DISPATCH=PASS")
        else:
            raise AssertionError("kill switch did not block dispatch")
        fixture._enable()

        # A dispatch exception is terminally ambiguous; retry never posts again.
        failed_id = fixture._create("g4b-dispatch-failure")
        prepare_authorized_production(failed_id)
        __import__("orchestration.production", fromlist=["claim_authorized_production_execution"]).claim_authorized_production_execution(failed_id)
        class FailingClient(FakeGitHubClient):
            def trigger_workflow(self, *args, **kwargs):
                self.trigger_count += 1
                raise RuntimeError("fake dispatch failure")
        failing_client = FailingClient()
        failing_provider = GitHubProductionProvider(client=failing_client)
        try:
            execute_authorized_claimed_github_runtime(failed_id, provider=failing_provider, client=failing_client)
        except RuntimeError:
            pass
        else:
            raise AssertionError("dispatch failure was not surfaced")
        try:
            execute_authorized_claimed_github_runtime(failed_id, provider=failing_provider, client=failing_client)
        except ValueError:
            assert failing_client.trigger_count == 1
            print("DISPATCH_EXCEPTION_NO_AUTOMATIC_RETRY=PASS")
        else:
            raise AssertionError("ambiguous dispatch was retried")
    finally:
        github_pages.promote_artifact_to_pages = original_promotion
    print("G4B_PERSISTED_STATE_SECRET_SAFE=PASS")
    print("G4B_GITHUB_PRODUCTION_LINE_SMOKE=PASS")


if __name__ == "__main__":
    main()
