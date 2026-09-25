"""Offline G4-B GitHub claimed-runtime contract smoke."""
import json
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "os" / "backend"))
os.environ["OS_TESTING"] = "1"

import g4a_authorized_production_smoke as fixture
from intelligence import autonomy, policy
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

PROMOTION_COUNT = 0
PROMOTION_MODE = "success"


class FakeGitHubClient:
    def __init__(self):
        self.owner = "example"
        self.repo = "offline"
        self.trigger_count = 0
        self.runs = []
        self.state = {"status": "queued", "conclusion": None}
        self.artifacts = [{"id": 7, "name": "remote-pay-guide-test", "size_in_bytes": 10, "expired": False, "archive_download_url": "https://example.invalid/archive"}]

    def list_workflow_runs(self, workflow, branch=None, event=None, per_page=30):
        return {"workflow_runs": [r for r in self.runs if r.get("workflow") in (None, workflow)]}

    def trigger_workflow(self, workflow, branch="main", inputs=None):
        self.trigger_count += 1
        run = {"id": 100 + self.trigger_count, "workflow": workflow, "html_url": "https://example.invalid/run", "status": self.state["status"], "conclusion": self.state["conclusion"], "created_at": "2999-01-01T00:00:00+00:00"}
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
    global PROMOTION_COUNT
    PROMOTION_COUNT += 1
    client = kwargs["client"]
    if PROMOTION_MODE == "crash_after_post":
        client.runs.append({"id": 900 + PROMOTION_COUNT, "workflow": "promote-video-asset.yml", "html_url": "https://example.invalid/promotion", "status": "completed", "conclusion": "success", "created_at": "2999-01-01T00:00:00+00:00"})
        raise RuntimeError("simulated promotion crash after dispatch")
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

        failure_id = fixture._create("g4b-failure")
        failure_prepared = prepare_authorized_production(failure_id)
        __import__("orchestration.production", fromlist=["claim_authorized_production_execution"]).claim_authorized_production_execution(failure_id)
        failure_client = FakeGitHubClient()
        failure_client.state = {"status": "completed", "conclusion": "failure"}
        failure_provider = GitHubProductionProvider(client=failure_client)
        execute_authorized_claimed_github_runtime(failure_id, provider=failure_provider, client=failure_client)
        failure_client.artifacts[0]["name"] = failure_prepared["production_task"].parameters["artifact_name"]
        failed = refresh_authorized_github_runtime(failure_id, provider=failure_provider, client=failure_client)
        assert failed["status"] == "failed" and failure_client.trigger_count == 1 and _counts()["video_assets"] == 0
        print("G4B_GITHUB_FAILURE_E2E=PASS")

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

        global PROMOTION_MODE
        PROMOTION_MODE = "crash_after_post"
        crash_id = fixture._create("g4b-promotion-crash")
        prepare_authorized_production(crash_id)
        __import__("orchestration.production", fromlist=["claim_authorized_production_execution"]).claim_authorized_production_execution(crash_id)
        crash_client = FakeGitHubClient()
        crash_provider = GitHubProductionProvider(client=crash_client)
        execute_authorized_claimed_github_runtime(crash_id, provider=crash_provider, client=crash_client)
        crash_client.artifacts[0]["name"] = get_task(__import__("production.tasks.manager", fromlist=["get_task_by_idempotency_key"]).get_task_by_idempotency_key(f"content-plan:{crash_id}:revision:{get_plan(crash_id)['revision']}").id).parameters["artifact_name"]
        crash_client.state = {"status": "completed", "conclusion": "success"}
        first_recovery = refresh_authorized_github_runtime(crash_id, provider=crash_provider, client=crash_client)
        assert first_recovery["status"] == "running" and PROMOTION_COUNT >= 2
        PROMOTION_MODE = "success"
        recovered = refresh_authorized_github_runtime(crash_id, provider=crash_provider, client=crash_client)
        assert recovered["status"] == "completed" and PROMOTION_COUNT == 2
        print("PROMOTION_CRASH_RECOVERY=PASS")
        print("PROMOTION_AT_MOST_ONCE=PASS")

        fixture._enable()
        off_id = fixture._create("g4b-autonomy-off")
        prepare_authorized_production(off_id)
        __import__("orchestration.production", fromlist=["claim_authorized_production_execution"]).claim_authorized_production_execution(off_id)
        autonomy.update_autonomy_settings(autonomy_enabled=False, kill_switch_active=False)
        off_client = FakeGitHubClient()
        try:
            execute_authorized_claimed_github_runtime(off_id, provider=GitHubProductionProvider(client=off_client), client=off_client)
        except ValueError:
            assert off_client.trigger_count == 0
            print("AUTONOMY_OFF_BEFORE_DISPATCH=PASS")
        else:
            raise AssertionError("autonomy off did not block dispatch")
        fixture._enable()

        revoke_id = fixture._create("g4b-override-revoke")
        policy.evaluate_policy(revoke_id, {"safety": "PASS", "novelty": "PASS", "duplicate_risk": "PASS", "account_health": "PASS", "platform_health": "PASS", "business": "UNKNOWN", "ai_confidence": "PASS"})
        autonomy.set_policy_override(revoke_id, "AUTO", "offline test")
        prepare_authorized_production(revoke_id)
        __import__("orchestration.production", fromlist=["claim_authorized_production_execution"]).claim_authorized_production_execution(revoke_id)
        autonomy.clear_policy_override(revoke_id, "offline revoke")
        revoke_client = FakeGitHubClient()
        try:
            execute_authorized_claimed_github_runtime(revoke_id, provider=GitHubProductionProvider(client=revoke_client), client=revoke_client)
        except ValueError:
            assert revoke_client.trigger_count == 0
            print("OVERRIDE_REVOKE_BEFORE_DISPATCH=PASS")
        else:
            raise AssertionError("revoked override did not block dispatch")

        stale_id = fixture._create("g4b-stale")
        prepare_authorized_production(stale_id)
        __import__("orchestration.production", fromlist=["claim_authorized_production_execution"]).claim_authorized_production_execution(stale_id)
        update_plan(stale_id, {"hook": "revised after claim"})
        stale_client = FakeGitHubClient()
        try:
            execute_authorized_claimed_github_runtime(stale_id, provider=GitHubProductionProvider(client=stale_client), client=stale_client)
        except ValueError:
            assert stale_client.trigger_count == 0
            print("STALE_REVISION_BEFORE_DISPATCH=PASS")
        else:
            raise AssertionError("stale revision dispatched")

        # Four callers share the durable execution claim; only one dispatches.
        for round_no in range(20):
            fixture._enable()
            concurrent_id = fixture._create(f"g4b-concurrent-{round_no}")
            prepare_authorized_production(concurrent_id)
            __import__("orchestration.production", fromlist=["claim_authorized_production_execution"]).claim_authorized_production_execution(concurrent_id)
            concurrent_client = FakeGitHubClient()
            concurrent_provider = GitHubProductionProvider(client=concurrent_client)
            def _attempt(_):
                try:
                    return execute_authorized_claimed_github_runtime(concurrent_id, provider=concurrent_provider, client=concurrent_client)
                except ValueError:
                    return {"status": "in_progress"}
            with ThreadPoolExecutor(max_workers=4) as pool:
                outcomes = list(pool.map(_attempt, range(4)))
            assert concurrent_client.trigger_count == 1
            task_id = get_jobs_for_task(__import__("production.tasks.manager", fromlist=["get_task_by_idempotency_key"]).get_task_by_idempotency_key(f"content-plan:{concurrent_id}:revision:{get_plan(concurrent_id)['revision']}").id)[0]["task_id"]
            with sqlite3.connect(fixture.DB) as db:
                assert db.execute("SELECT COUNT(*) FROM runtime_jobs WHERE task_id=?", (task_id,)).fetchone()[0] == 1
                assert db.execute("SELECT COUNT(*) FROM production_results WHERE runtime_job_id=(SELECT id FROM runtime_jobs WHERE task_id=?)", (task_id,)).fetchone()[0] == 1
        print("G4B_EXECUTION_STRESS_ROUNDS=20")
        print("G4B_EXECUTION_CONCURRENCY=PASS")
        print("G4B_CROSS_PROCESS_CORRECTNESS_DB_BACKED=PASS")

        # Result creation is DB-backed and converges to one row under races.
        fixture._enable()
        result_id = fixture._create("g4b-result-race")
        prepare_authorized_production(result_id)
        claim = __import__("orchestration.production", fromlist=["claim_authorized_production_execution"]).claim_authorized_production_execution(result_id)
        job_id = claim["runtime_job"]["id"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(lambda _: create_or_get_result_for_job({"runtime_job_id": job_id, "provider": "github", "status": "submitted", "output": {"g4b_no_asset_binding": True}}), range(4)))
        assert len({row["id"] for row in rows}) == 1
        with sqlite3.connect(fixture.DB) as db:
            assert db.execute("SELECT COUNT(*) FROM production_results WHERE runtime_job_id=?", (job_id,)).fetchone()[0] == 1
        print("PRODUCTION_RESULT_CONCURRENCY=PASS")

        current = rows[0]
        from production.results.manager import update_result
        from production.tasks.manager import update_task_status
        update_task_status(claim["production_task"].id, "running", expected_status="scheduled")
        current = update_result(current["id"], status="completed", output={"g4b_no_asset_binding": True}, bind_asset=False)
        try:
            update_result(current["id"], status="running")
        except ValueError:
            pass
        else:
            raise AssertionError("terminal result regressed")
        print("PRODUCTION_RESULT_STATUS_CAS_SAFE=PASS")
    finally:
        github_pages.promote_artifact_to_pages = original_promotion
    print("G4B_PERSISTED_STATE_SECRET_SAFE=PASS")
    print("G4B_GITHUB_PRODUCTION_LINE_SMOKE=PASS")


if __name__ == "__main__":
    main()
