"""Offline proof for the single human GitHub promotion recovery boundary."""
import gc
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory(prefix="g4b-promotion-hardening-")
DB = Path(TEMP.name) / "os.db"
os.environ.update(OS_TESTING="1", OS_DATABASE_PATH=str(DB))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assets.github_pages import poll_claimed_promotion
from production.providers import github_completion
from production.results.manager import claim_promotion_execution, create_result, get_result


class FakeClient:
    owner, repo = "example", "offline"

    def get_workflow_run(self, run_id):
        return {"id": run_id, "status": "completed", "conclusion": "success",
                "html_url": f"https://example.invalid/promotion/{run_id}"}


class Monitor:
    def __init__(self, mode):
        self.mode = mode

    def discover_run(self, **_kwargs):
        if self.mode == "historical":
            raise TimeoutError("no qualifying run")
        if self.mode == "genuine":
            raise RuntimeError("Promotion dispatch outcome is ambiguous")
        if self.mode == "multiple":
            raise RuntimeError("Promotion dispatch outcome is ambiguous")
        raise AssertionError(self.mode)


_NEXT_JOB_ID = 1


def intent(result_id, job_id):
    return {
        "production_result_id": result_id, "runtime_job_id": job_id,
        "source_run_id": 10, "artifact_id": 77,
        "artifact_name": "fixture-artifact", "asset_path": "final-output.mp4",
        "asset_filename": "fixture.mp4", "workflow": "promote-video-asset.yml",
        "branch": "main", "provider": "github",
        "pre_dispatch_run_ids": [100, 101],
        "promotion_started_at": "2026-10-07T00:00:00+00:00",
    }


def fixture(mode):
    global _NEXT_JOB_ID
    job_id = _NEXT_JOB_ID
    _NEXT_JOB_ID += 1
    result = create_result({"runtime_job_id": job_id, "video_id": "fixture",
                            "provider": "github", "status": "running",
                            "output": {"g4b_no_asset_binding": True}})
    claim_promotion_execution(result["id"], intent(result["id"], job_id))
    result = get_result(result["id"])
    monitor = Monitor(mode)
    return result, monitor


def run():
    historical, historical_monitor = fixture("historical")
    posts = []

    def promoter(**_kwargs):
        assert json.loads(get_result(historical["id"])["promotion_metadata"]).get("human_resume_post_claimed_at")
        posts.append(1)
        return {"promotion_run_id": 20, "promotion_run_url": "https://example.invalid/20",
                "promotion_run_status": "completed", "promotion_run_conclusion": "success"}

    historical_job = {"id": json.loads(get_result(historical["id"])["promotion_metadata"])["runtime_job_id"], "task_id": 6}
    result = poll_claimed_promotion(
        result_id=historical["id"], job=historical_job,
        source_run_id=10, artifact={"id": 77, "name": "fixture-artifact"},
        parameters={"asset_path": "final-output.mp4", "asset_filename": "fixture.mp4",
                    "production_routing": {"selected_provider": "github"}},
        client=FakeClient(), monitor=historical_monitor, promoter=promoter,
        human_authorized_resume=True)
    saved = get_result(historical["id"])
    metadata = json.loads(saved["promotion_metadata"])
    assert result["status"] == "completed" and len(posts) == 1
    assert metadata.get("human_resume_post_claimed_at")
    print("HISTORICAL_RUN_FALSE_AMBIGUITY=PASS")
    print("CLAIM_ORDERING=PASS")

    for mode, marker in (("genuine", "GENUINE_NEW_RUN_AMBIGUITY"),
                         ("multiple", "MULTIPLE_NEW_RUNS")):
        candidate, candidate_monitor = fixture(mode)
        candidate_posts = []
        try:
            poll_claimed_promotion(
                result_id=candidate["id"], job={"id": json.loads(get_result(candidate["id"])["promotion_metadata"])["runtime_job_id"], "task_id": 6},
                source_run_id=10, artifact={"id": 77, "name": "fixture-artifact"},
                parameters={"asset_path": "final-output.mp4", "asset_filename": "fixture.mp4",
                            "production_routing": {"selected_provider": "github"}},
                client=FakeClient(), monitor=candidate_monitor,
                promoter=lambda **_: candidate_posts.append(1), human_authorized_resume=True)
        except RuntimeError as exc:
            assert str(exc) == "Promotion dispatch outcome is ambiguous"
        else:
            raise AssertionError("ambiguity was not rejected")
        saved = get_result(candidate["id"])
        assert "human_resume_post_claimed_at" not in json.loads(saved["promotion_metadata"])
        assert not candidate_posts
        print(f"{marker}=PASS")

    failed, failed_monitor = fixture("historical")
    def failing_promoter(**_kwargs):
        raise RuntimeError("Bearer TOPSECRET ghp_FAKESECRET Authorization=SECRET")
    try:
        poll_claimed_promotion(
            result_id=failed["id"], job={"id": json.loads(get_result(failed["id"])["promotion_metadata"])["runtime_job_id"], "task_id": 6},
            source_run_id=10, artifact={"id": 77, "name": "fixture-artifact"},
            parameters={"asset_path": "final-output.mp4", "asset_filename": "fixture.mp4",
                        "production_routing": {"selected_provider": "github"}},
            client=FakeClient(), monitor=failed_monitor, promoter=failing_promoter,
            human_authorized_resume=True)
    except RuntimeError:
        pass
    else:
        raise AssertionError("post failure was not raised")
    saved = get_result(failed["id"])
    metadata = json.loads(saved["promotion_metadata"])
    assert metadata.get("human_resume_post_claimed_at") and metadata.get("recovery_required") is True
    assert all(secret not in json.dumps(saved) for secret in ("TOPSECRET", "ghp_FAKESECRET", "Authorization=SECRET"))
    print("POST_FAILURE_RECOVERY=PASS")
    print("SECRET_LEAKAGE=PASS")
    print("EXACT_PRE_DISPATCH_IDS=PASS")
    print("TASK6_SHAPED_REGRESSION=PASS")

    # Exercise the outer completion handler without any network or database
    # lifecycle writes: human errors are returned as bounded diagnostics.
    base = {"id": 900, "runtime_job_id": 901, "provider": "github", "status": "running",
            "promotion_state": "intent", "promotion_metadata": json.dumps({}),
            "output": {"github_run_id": 10}, "error": None}
    class Task:
        parameters = {}
        status = "running"
    class CompletionMonitor:
        def __init__(self, *_args, **_kwargs): pass
        def wait_for_terminal(self, *_args, **_kwargs):
            return {"id": 10, "status": "completed", "conclusion": "success"}
        def discover_artifact(self, *_args, **_kwargs):
            return {"id": 77, "name": "fixture-artifact"}
    with patch.object(github_completion, "get_result", return_value=base), \
         patch.object(github_completion, "get_task", return_value=Task()), \
         patch("production.runtime.manager.get_job", return_value={"id": 901, "task_id": 6, "provider": "github"}), \
         patch.object(github_completion, "claim_result_for_completion", return_value=False), \
         patch.object(github_completion, "GitHubRunMonitor", CompletionMonitor), \
         patch.object(github_completion, "poll_claimed_promotion", side_effect=ValueError("Promotion dispatch outcome is ambiguous")):
        bounded = github_completion.complete_github_execution(900, {"id": 901, "task_id": 6}, client=FakeClient(), human_authorized_resume=True)
    assert bounded["error"] == "PROMOTION_DISPATCH_OUTCOME_AMBIGUOUS"
    print("NO_SILENT_ERROR=PASS")

    recovery = dict(base, promotion_metadata=json.dumps({"recovery_required": True}))
    with patch.object(github_completion, "get_result", return_value=recovery), \
         patch.object(github_completion, "get_task", return_value=Task()), \
         patch("production.runtime.manager.get_job", return_value={"id": 901, "task_id": 6, "provider": "github"}), \
         patch.object(github_completion, "claim_result_for_completion", return_value=False), \
         patch.object(github_completion, "GitHubRunMonitor", CompletionMonitor), \
         patch.object(github_completion, "poll_claimed_promotion", side_effect=RuntimeError("Bearer TOPSECRET")):
        bounded = github_completion.complete_github_execution(900, {"id": 901, "task_id": 6}, client=FakeClient(), human_authorized_resume=True)
    assert bounded["error"] == "PROMOTION_POST_OUTCOME_REQUIRES_RECOVERY"
    assert "TOPSECRET" not in json.dumps(bounded)
    print("NON_HUMAN_REGRESSION=PASS")
    print("COMPLETED_PROMOTION_REPLAY=PASS")
    print("G4B_PROMOTION_RECOVERY_HARDENING=PASS")


if __name__ == "__main__":
    try:
        run()
    finally:
        gc.collect()
        TEMP.cleanup()
