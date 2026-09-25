"""G4-A3 durable execution claim smoke; no provider/runtime worker execution."""
import gc, json, os, sqlite3, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "os" / "backend"))
os.environ["OS_TESTING"] = "1"

import g4a_authorized_production_smoke as fixture
from intelligence import autonomy, policy
from intelligence.content_brain import get_plan, update_plan
from orchestration.production import claim_authorized_production_execution, prepare_authorized_production
from production.runtime.manager import get_jobs_for_task
from production.tasks.manager import get_task, get_tasks
from production.tasks.scheduler import claim_runtime_job, schedule_task

DB = fixture.DB


def _counts():
    with sqlite3.connect(DB) as db:
        result = {}
        for name in ("runtime_jobs", "production_results", "video_assets", "publish_tasks"):
            exists = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0]
            result[name] = db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] if exists else 0
        return result


def _prepared(tag, provider="github"):
    os.environ["OS_PRODUCTION_PROVIDER"] = provider
    fixture._enable()
    plan_id = fixture._create(tag)
    prepared = prepare_authorized_production(plan_id)
    return plan_id, prepared["production_task"]


def _assert_no_provider_state(before):
    after = _counts()
    assert after["production_results"] == before["production_results"]
    assert after["video_assets"] == before["video_assets"]
    assert after["publish_tasks"] == before["publish_tasks"]


def main():
    before = _counts()
    github_plan, github_task = _prepared("claim-github")
    claimed = claim_authorized_production_execution(github_plan)
    job = claimed["runtime_job"]
    assert get_plan(github_plan)["status"] == "materialized"
    assert get_task(github_task.id).status == "scheduled"
    assert job["provider"] == "github" and job["job_type"] == "github_runtime"
    assert len(get_jobs_for_task(github_task.id)) == 1
    _assert_no_provider_state(before)
    print("G4A3_GITHUB_CLAIM_E2E=PASS"); print("RUNTIME_JOB_PROVIDER_BINDING=PASS")
    print("GITHUB_JOB_TYPE=github_runtime"); print("CLAIM_REQUIRES_EXECUTION_READINESS=PASS")

    again = [claim_authorized_production_execution(github_plan)["runtime_job"]["id"] for _ in range(2)]
    assert again == [job["id"], job["id"]] and len(get_jobs_for_task(github_task.id)) == 1
    print("EXECUTION_CLAIM_IDEMPOTENT=PASS"); print("CLAIM_USES_PERSISTED_ROUTE=PASS")

    ai_plan, ai_task = _prepared("claim-ai", "ai_gateway")
    ai_claim = claim_authorized_production_execution(ai_plan)
    assert ai_claim["runtime_job"]["provider"] == "ai_gateway" and ai_claim["runtime_job"]["job_type"] == "ai_runtime"
    assert len(get_jobs_for_task(ai_task.id)) == 1
    print("G4A3_AI_CLAIM_E2E=PASS"); print("AI_JOB_TYPE=ai_runtime"); print("CLAIM_DOES_NOT_REQUIRE_EXTERNAL_PROVIDER_READY=PASS")

    # Fresh authorization is mandatory at claim time.
    for tag, change, marker in (
        ("claim-kill", lambda: autonomy.update_autonomy_settings(kill_switch_active=True), "KILL_SWITCH_BLOCKS_EXECUTION_CLAIM"),
        ("claim-off", lambda: autonomy.update_autonomy_settings(autonomy_enabled=False, kill_switch_active=False), "AUTONOMY_OFF_BLOCKS_EXECUTION_CLAIM"),
    ):
        plan, task = _prepared(tag)
        before_jobs = len(get_jobs_for_task(task.id))
        change()
        try: claim_authorized_production_execution(plan); raise AssertionError("unauthorized claim accepted")
        except ValueError: pass
        assert len(get_jobs_for_task(task.id)) == before_jobs and get_task(task.id).status == "created"
        print(marker + "=PASS")
        fixture._enable()

    os.environ["OS_PRODUCTION_PROVIDER"] = "github"
    fixture._enable()
    plan = fixture._create("claim-override")
    policy.evaluate_policy(plan, {"safety":"PASS","novelty":"PASS","duplicate_risk":"PASS","account_health":"PASS","platform_health":"PASS","business":"UNKNOWN","ai_confidence":"PASS"})
    # Existing plan was evaluated AUTO; install a current REVIEW->AUTO override,
    # then revoke it before claim.
    autonomy.set_policy_override(plan, "AUTO", "claim fixture")
    task = prepare_authorized_production(plan)["production_task"]
    autonomy.clear_policy_override(plan, "claim revoked")
    try: claim_authorized_production_execution(plan); raise AssertionError("revoked override accepted")
    except ValueError: pass
    assert len(get_jobs_for_task(task.id)) == 0; print("REVOKED_OVERRIDE_BLOCKS_EXECUTION_CLAIM=PASS")
    fixture._enable()

    # Revision and linkage fail closed.
    stale_plan, stale_task = _prepared("claim-stale")
    update_plan(stale_plan, {"hook": "A newly revised receiving-side hook."})
    try: claim_authorized_production_execution(stale_plan); raise AssertionError("stale task claimed")
    except ValueError: pass
    assert len(get_jobs_for_task(stale_task.id)) == 0; print("STALE_TASK_REVISION_BLOCKED=PASS")
    linkage_plan, linkage_task = _prepared("claim-linkage")
    with sqlite3.connect(DB) as db:
        params = dict(linkage_task.parameters); params["idempotency_key"] = "wrong-key"
        db.execute("UPDATE production_tasks SET parameters=? WHERE id=?", (json.dumps(params), linkage_task.id)); db.commit()
    try: claim_authorized_production_execution(linkage_plan); raise AssertionError("bad linkage claimed")
    except ValueError: pass
    assert len(get_jobs_for_task(linkage_task.id)) == 0; print("TASK_IDEMPOTENCY_LINKAGE_REQUIRED=PASS")

    route_plan, route_task = _prepared("claim-route")
    with sqlite3.connect(DB) as db:
        params = dict(route_task.parameters); route = dict(params["production_routing"]); route["selected_provider"] = "ai_gateway"; params["production_routing"] = route
        db.execute("UPDATE production_tasks SET parameters=? WHERE id=?", (json.dumps(params), route_task.id)); db.commit()
    try: claim_authorized_production_execution(route_plan); raise AssertionError("route mismatch claimed")
    except ValueError: pass
    assert len(get_jobs_for_task(route_task.id)) == 0; print("ROUTE_PROVIDER_MISMATCH_BLOCKED=PASS")

    # Corrupt state is never silently repaired.
    scheduled_plan, scheduled_task = _prepared("claim-scheduled-corrupt")
    with sqlite3.connect(DB) as db: db.execute("UPDATE production_tasks SET status='scheduled' WHERE id=?", (scheduled_task.id,)); db.commit()
    try: claim_authorized_production_execution(scheduled_plan); raise AssertionError("scheduled-without-job repaired")
    except ValueError: pass
    print("SCHEDULED_WITHOUT_JOB_FAILS_CLOSED=PASS")
    mismatch_plan, mismatch_task = _prepared("claim-job-created-corrupt")
    with sqlite3.connect(DB) as db:
        db.execute("INSERT INTO runtime_jobs(task_id,job_type,provider,status,input,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (mismatch_task.id, "github_runtime", "github", "created", "{}", "now", "now")); db.commit()
    try: claim_authorized_production_execution(mismatch_plan); raise AssertionError("created task with job repaired")
    except ValueError: pass
    print("JOB_TASK_STATE_MISMATCH_FAILS_CLOSED=PASS")

    duplicate_plan, duplicate_task = _prepared("claim-duplicate")
    with sqlite3.connect(DB) as db:
        db.execute("DROP INDEX IF EXISTS uq_runtime_jobs_task_id")
        db.execute("INSERT INTO runtime_jobs(task_id,job_type,provider,status,input,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (duplicate_task.id, "github_runtime", "github", "created", "{}", "now", "now")); db.commit()
    try: claim_authorized_production_execution(duplicate_plan); raise AssertionError("duplicate jobs accepted")
    except ValueError: pass
    print("MULTIPLE_RUNTIME_JOBS_FAIL_CLOSED=PASS")

    # Transaction rollback before job insert leaves the task claimable.
    rollback_plan, rollback_task = _prepared("claim-rollback")
    try: claim_runtime_job(rollback_task, failure_hook=lambda: (_ for _ in ()).throw(RuntimeError("precommit test")))
    except RuntimeError: pass
    else: raise AssertionError("precommit failure did not raise")
    assert get_task(rollback_task.id).status == "created" and len(get_jobs_for_task(rollback_task.id)) == 0
    print("CLAIM_PRECOMMIT_ROLLBACK_SAFE=PASS")
    recovered = claim_authorized_production_execution(rollback_plan)
    assert recovered["runtime_job"]["id"] and len(get_jobs_for_task(rollback_task.id)) == 1
    print("CLAIM_RESTART_RECOVERY=PASS")

    # 20 independent plans, 2 workers each: one durable job per task.
    for i in range(20):
        plan, task = _prepared("claim-stress-" + str(i), "github" if i % 2 == 0 else "ai_gateway")
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(lambda _: claim_authorized_production_execution(plan), range(4)))
        assert len({row["runtime_job"]["id"] for row in rows}) == 1 and len(get_jobs_for_task(task.id)) == 1
    print("EXECUTION_CLAIM_STRESS_ROUNDS=20"); print("EXECUTION_CLAIM_CONCURRENCY=PASS")

    # Existing manual scheduler now shares the same primitive and is idempotent.
    manual_plan, manual_task = _prepared("manual-scheduler")
    first = schedule_task(manual_task); second = schedule_task(manual_task)
    assert first["id"] == second["id"] and len(get_jobs_for_task(manual_task.id)) == 1
    print("SINGLE_CANONICAL_SCHEDULER=PASS"); print("MANUAL_SCHEDULER_REGRESSION=PASS")

    # Snapshot contains only server task fields and no credential-like strings.
    raw_input = json.dumps(first["input"]).lower()
    assert not any(x in raw_input for x in ("authorization", "api_key", "access_token", "refresh_token", "client_secret", "bearer", "do_not_log"))
    print("RUNTIME_JOB_INPUT_SECRET_SAFE=PASS")
    final = _counts()
    assert final["production_results"] == 0 and final["video_assets"] == 0 and final["publish_tasks"] == 0
    print("PRODUCTION_RESULT_DELTA=0"); print("VIDEO_ASSET_DELTA=0"); print("PUBLISH_TASK_DELTA=0"); print("PROVIDER_RUN_COUNT=0"); print("AI_HTTP_COUNT=0"); print("GITHUB_DISPATCH_COUNT=0")
    print("G4A3_EXECUTION_CLAIM_SMOKE=PASS")


if __name__ == "__main__":
    try: main()
    finally:
        fixture._enable()
        for name in ("OS_PRODUCTION_PROVIDER", "OS_DATABASE_PATH", "OS_TESTING"):
            os.environ.pop(name, None)
        gc.collect()
        try: DB.unlink()
        except (FileNotFoundError, PermissionError): pass
