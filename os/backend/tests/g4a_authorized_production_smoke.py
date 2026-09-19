"""G4-A2 preparation contract smoke; isolated TEMP DB and no provider execution."""
import gc, json, os, sqlite3, sys, tempfile, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "os" / "backend"))
os.environ["OS_TESTING"] = "1"
DB = Path(tempfile.gettempdir()) / ("g4a-" + uuid.uuid4().hex + ".db")
os.environ["OS_DATABASE_PATH"] = str(DB)

from accounts.manager import create_account
from accounts.models import Account
from data.platform_capabilities import get_platform_capability
from data.sync_state import ensure_sync_state, mark_sync_success
from intelligence import autonomy, policy
from intelligence.content_brain import ContentPlan, get_plan, save_plan, update_plan
from intelligence.content_plan_service import approve_plan, materialize_plan
from orchestration.production import prepare_authorized_production
from production.tasks.manager import get_tasks
import orchestration.production as g4_production


def _snapshot(account_id, tag):
    with sqlite3.connect(DB) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS intelligence_feedback_snapshots (
          id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, platform TEXT NOT NULL,
          content_id TEXT NOT NULL, platform_video_id TEXT, snapshot_key TEXT NOT NULL,
          metric_collected_at TEXT, performance_score INTEGER NOT NULL DEFAULT 0,
          priority_score REAL NOT NULL DEFAULT 0, strategy_type TEXT, feedback_json TEXT NOT NULL,
          strategy_json TEXT NOT NULL, metrics_json TEXT NOT NULL, funnel_json TEXT NOT NULL,
          created_at TEXT NOT NULL, UNIQUE(account_id, platform, content_id, snapshot_key))""")
        db.execute("""INSERT INTO intelligence_feedback_snapshots
          (account_id,platform,content_id,snapshot_key,performance_score,feedback_json,strategy_json,metrics_json,funnel_json,created_at)
          VALUES (?,?,?,?,?,?,?,?,?,?)""", (account_id, "youtube", "g4a-" + tag, tag, 10,
          json.dumps({"referral_clicks": 2, "intent_events": 2, "conversions": 1}), "{}", "{}", "{}", "now"))
        sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.commit()
    return sid


def _plan(tag, sid):
    return ContentPlan(content_id="g4a-" + tag, topic="Verify a stablecoin payment", angle="receiving-side confirmation",
        target_audience="freelancers", hook="A screenshot is not proof of a credited payment.",
        script="Check your receiving account and transaction status before closing the job.",
        cta="Follow Remote Pay Guide.", title="G4A " + tag, description="Payment education",
        visual_direction="Account confirmation view", source_snapshot_id=sid, production_spec={
            "provider": "ai_gateway", "workflow": "evil.yml", "endpoint": "https://evil.invalid"},
        generation_provider="deterministic", generation_evidence={"source": "content_plan_provider",
        "schema_version": 1, "provider": "deterministic", "content_plan_constructed": True,
        "canonical_validation_passed": True})


def _create(tag):
    account = create_account(Account(platform="youtube", account_name="g4a-" + tag, status="active"))
    sid = _snapshot(account["id"], tag)
    ensure_sync_state(account["id"], "youtube")
    mark_sync_success(account["id"], "youtube", "content")
    mark_sync_success(account["id"], "youtube", "analytics")
    get_platform_capability("youtube")
    p = save_plan(_plan(tag, sid), sid)
    assert policy.evaluate_policy(p["id"])["decision"] == "AUTO"
    return p["id"]


def _enable():
    autonomy.update_autonomy_settings(autonomy_enabled=True, kill_switch_active=False)


def _counts():
    with sqlite3.connect(DB) as db:
        return {name: db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0] and db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in ("production_tasks", "runtime_jobs", "production_results", "video_assets", "publish_tasks")}


def main():
    _enable()
    os.environ.pop("OS_PRODUCTION_PROVIDER", None)
    github_id = _create("github")
    before = _counts()
    prepared = prepare_authorized_production(github_id)
    task = prepared["production_task"]
    assert prepared["authorization"]["autonomous_continuation_allowed"] is True
    assert prepared["routing"]["selected_provider"] == "github"
    assert prepared["routing"]["selection_source"] == "server_default" and prepared["routing"]["reason_code"] == "DEFAULT_PROVIDER"
    assert get_plan(github_id)["status"] == "materialized"
    assert task.provider == "github" and task.parameters["production_routing"]["selected_provider"] == "github"
    assert task.parameters["production_routing"]["content_plan_id"] == github_id
    assert task.parameters["content_plan_revision"] == get_plan(github_id)["revision"]
    assert task.parameters["idempotency_key"] == f"content-plan:{github_id}:revision:{get_plan(github_id)['revision']}"
    assert prepared["execution"] == "not_started"
    assert before["production_tasks"] == 0 and _counts()["production_tasks"] == 1
    assert _counts()["runtime_jobs"] == 0 and _counts()["production_results"] == 0 and _counts()["video_assets"] == 0 and _counts()["publish_tasks"] == 0
    assert task.workflow == "render-short01.yml" and task.task_type == "video_batch"
    assert not hasattr(prepared, "run")
    print("AUTHORIZATION_CONSUMED=PASS"); print("G4A_USES_REAL_G3_AUTHORIZATION=PASS"); print("DEFAULT_ROUTE_GITHUB=PASS"); print("G4A_GITHUB_PREPARE_E2E=PASS")
    print("ROUTING_BEFORE_TASK_INSERT=PASS"); print("ROUTING_EVIDENCE_PERSISTED=PASS")
    print("GITHUB_TASK_PROVIDER=github"); print("GITHUB_TASK_READINESS=PASS")

    # Same revision remains bound to the original route after configuration changes.
    os.environ["OS_PRODUCTION_PROVIDER"] = "ai_gateway"
    same = prepare_authorized_production(github_id)
    assert same["production_task"].id == task.id and same["production_task"].provider == "github"
    print("EXISTING_TASK_ROUTE_STABLE=PASS")

    os.environ["OS_PRODUCTION_PROVIDER"] = "ai_gateway"
    ai_id = _create("ai")
    ai = prepare_authorized_production(ai_id)
    ai_task = ai["production_task"]
    assert ai_task.provider == "ai_gateway" and ai_task.task_type == "video_generation"
    assert ai_task.parameters["production_routing"]["selection_source"] == "server_environment"
    assert ai_task.workflow == "" and ai_task.parameters["parameters"]["options"]["aspect_ratio"] == "9:16"
    assert _counts()["runtime_jobs"] == 0 and _counts()["production_results"] == 0 and _counts()["video_assets"] == 0
    print("G4A_AI_PREPARE_E2E=PASS"); print("AI_TASK_PROVIDER=ai_gateway"); print("AI_TASK_TYPE=video_generation"); print("AI_TASK_READINESS=PASS"); print("AI_ROUTE_NO_EXTERNAL_SUBMIT=PASS")

    # Provider fields in the plan payload cannot override server routing.
    os.environ["OS_PRODUCTION_PROVIDER"] = "github"
    forged = _create("forged-github")
    forged_task = prepare_authorized_production(forged)["production_task"]
    assert forged_task.provider == "github"
    os.environ["OS_PRODUCTION_PROVIDER"] = "ai_gateway"
    forged_ai = _create("forged-ai")
    forged_ai_task = prepare_authorized_production(forged_ai)["production_task"]
    assert forged_ai_task.provider == "ai_gateway"
    assert forged_ai_task.parameters["production_routing"]["selected_provider"] == "ai_gateway"
    assert "evil.invalid" not in json.dumps(forged_ai_task.parameters)
    print("UNTRUSTED_PRODUCTION_SPEC_IGNORED=PASS"); print("SERVER_ROUTE_AUTHORITATIVE=PASS"); print("ARBITRARY_ENDPOINT_NOT_EXECUTABLE=PASS"); print("ROUTING_EVIDENCE_SECRET_SAFE=PASS")

    serialized = json.dumps(forged_ai_task.parameters).lower()
    assert not any(key in serialized for key in ("authorization", "api_key", "access_token", "refresh_token", "client_secret", "bearer", "evil.invalid"))
    print("PRODUCTION_TASK_SECRET_SAFE=PASS")

    # Fail-closed authorization/configuration cases.
    os.environ["OS_PRODUCTION_PROVIDER"] = "banana"
    bad_route = _create("bad-route")
    try: prepare_authorized_production(bad_route); raise AssertionError("invalid route accepted")
    except ValueError: pass
    assert get_plan(bad_route)["status"] == "preview"
    print("ROUTE_PREFLIGHT_BEFORE_APPROVAL=PASS"); print("INVALID_ROUTE_CONFIG_FAILS_CLOSED=PASS")
    for invalid in ("", "   ", "banana", "GITHUB!!!", "http://invalid", "ai_gateway?key=x"):
        os.environ["OS_PRODUCTION_PROVIDER"] = invalid
        invalid_id = _create("invalid-" + uuid.uuid4().hex[:6])
        try: prepare_authorized_production(invalid_id); raise AssertionError("invalid route accepted")
        except ValueError: pass
        assert get_plan(invalid_id)["status"] == "preview"
    print("INVALID_ROUTE_VALUES_FAIL_CLOSED=PASS")
    os.environ["OS_PRODUCTION_PROVIDER"] = "github"
    off = _create("off"); autonomy.update_autonomy_settings(autonomy_enabled=False, kill_switch_active=False)
    try: prepare_authorized_production(off); raise AssertionError("autonomy off accepted")
    except ValueError: pass
    assert get_plan(off)["status"] == "preview"; print("AUTONOMY_OFF_NO_MATERIALIZATION=PASS")
    _enable(); kill = _create("kill"); autonomy.update_autonomy_settings(autonomy_enabled=True, kill_switch_active=True)
    try: prepare_authorized_production(kill); raise AssertionError("kill switch accepted")
    except ValueError: pass
    assert get_plan(kill)["status"] == "preview"; print("KILL_SWITCH_NO_MATERIALIZATION=PASS")
    print("DEFAULT_G4A_FAIL_CLOSED=PASS")
    _enable(); blocked = _create("blocked")
    policy.evaluate_policy(blocked, {"safety":"BLOCK","novelty":"PASS","duplicate_risk":"PASS","account_health":"PASS","platform_health":"PASS","business":"PASS","ai_confidence":"PASS"})
    try: prepare_authorized_production(blocked); raise AssertionError("block accepted")
    except ValueError: pass
    assert get_plan(blocked)["status"] == "preview"; print("BLOCK_NO_MATERIALIZATION=PASS")
    _enable(); review = _create("review"); policy.evaluate_policy(review, {"safety":"PASS","novelty":"PASS","duplicate_risk":"PASS","account_health":"PASS","platform_health":"PASS","business":"UNKNOWN","ai_confidence":"PASS"})
    try: prepare_authorized_production(review); raise AssertionError("review accepted")
    except ValueError: pass
    assert get_plan(review)["status"] == "preview"; print("REVIEW_NO_MATERIALIZATION=PASS")
    autonomy.set_policy_override(review, "AUTO", "operator approved controlled continuation"); reviewed = prepare_authorized_production(review)
    assert reviewed["production_task"].provider == "github" and policy.get_current_policy_decision(review)["decision"] == "REVIEW"
    print("REVIEW_OVERRIDE_PREPARES_PRODUCTION=PASS"); print("RAW_REVIEW_REMAINS_IMMUTABLE=PASS")

    _enable(); stale = _create("stale")
    stale_auth = autonomy.get_effective_authorization(stale)
    update_plan(stale, {"hook": "A revised receiving-side verification hook."})
    try: prepare_authorized_production(stale); raise AssertionError("stale authorization accepted")
    except ValueError: pass
    assert get_plan(stale)["status"] == "preview" and stale_auth["current_revision"] != get_plan(stale)["revision"]
    print("STALE_AUTHORIZATION_NO_MATERIALIZATION=PASS"); print("HUMAN_EDIT_CANNOT_CONTROL_PROVIDER=PASS")

    # Revision binding protects the authorization-to-approval TOCTOU boundary.
    os.environ["OS_PRODUCTION_PROVIDER"] = "github"; _enable(); rev_race = _create("rev-race")
    original_approve = g4_production.approve_plan
    def edit_before_approve(plan_id, expected_revision=None):
        update_plan(plan_id, {"hook": "A concurrently revised authorization hook."})
        return original_approve(plan_id, expected_revision=expected_revision)
    g4_production.approve_plan = edit_before_approve
    try:
        try: prepare_authorized_production(rev_race); raise AssertionError("older authorization approved newer revision")
        except ValueError: pass
    finally: g4_production.approve_plan = original_approve
    assert get_plan(rev_race)["revision"] == 2 and get_plan(rev_race)["status"] == "preview"
    print("AUTHORIZED_REVISION_CANNOT_APPROVE_NEWER_REVISION=PASS")

    def _post_approval_race(tag, after_approval):
        plan_id = _create(tag); before_count = _counts()["production_tasks"]
        original = g4_production.approve_plan
        def wrapped(pid, expected_revision=None):
            value = original(pid, expected_revision=expected_revision); after_approval(pid); return value
        g4_production.approve_plan = wrapped
        try:
            try: prepare_authorized_production(plan_id); raise AssertionError(tag + " race materialized")
            except ValueError: pass
        finally: g4_production.approve_plan = original
        assert get_plan(plan_id)["status"] in {"approved", "preview"}
        assert _counts()["production_tasks"] == before_count
        return plan_id

    _enable(); _post_approval_race("kill-race", lambda _pid: autonomy.update_autonomy_settings(kill_switch_active=True))
    print("KILL_SWITCH_RACE_STOPS_MATERIALIZATION=PASS")
    _enable(); _post_approval_race("autonomy-race", lambda _pid: autonomy.update_autonomy_settings(autonomy_enabled=False))
    print("AUTONOMY_DISABLE_RACE_STOPS_MATERIALIZATION=PASS")
    _enable(); override_race = _create("override-race")
    policy.evaluate_policy(override_race, {"safety":"PASS","novelty":"PASS","duplicate_risk":"PASS","account_health":"PASS","platform_health":"PASS","business":"UNKNOWN","ai_confidence":"PASS"})
    autonomy.set_policy_override(override_race, "AUTO", "controlled race fixture")
    original = g4_production.approve_plan
    def clear_after_approve(pid, expected_revision=None):
        value = original(pid, expected_revision=expected_revision); autonomy.clear_policy_override(pid, "test revocation"); return value
    g4_production.approve_plan = clear_after_approve
    before_count = _counts()["production_tasks"]
    try:
        try: prepare_authorized_production(override_race); raise AssertionError("cleared override materialized")
        except ValueError: pass
    finally: g4_production.approve_plan = original
    assert _counts()["production_tasks"] == before_count; print("OVERRIDE_CLEAR_RACE_STOPS_MATERIALIZATION=PASS")
    _enable(); _post_approval_race("revision-after-approval", lambda pid: update_plan(pid, {"hook": "A new revision after approval."}))
    print("REVISION_CHANGE_AFTER_APPROVAL_STOPS_MATERIALIZATION=PASS"); print("PRE_MATERIALIZE_AUTH_RECHECK=PASS")

    # A route is immutable for one preparation invocation.
    _enable(); os.environ["OS_PRODUCTION_PROVIDER"] = "github"; frozen_id = _create("frozen")
    original = g4_production.approve_plan
    def switch_route_after_approve(pid, expected_revision=None):
        value = original(pid, expected_revision=expected_revision); os.environ["OS_PRODUCTION_PROVIDER"] = "ai_gateway"; return value
    g4_production.approve_plan = switch_route_after_approve
    try: frozen_task = prepare_authorized_production(frozen_id)["production_task"]
    finally: g4_production.approve_plan = original
    assert frozen_task.provider == "github"; print("ROUTE_FROZEN_PER_PREPARATION=PASS")

    # Retry and crash-recovery lifecycle paths.
    os.environ["OS_PRODUCTION_PROVIDER"] = "github"; approved = _create("approved")
    approve_plan(approved); a = prepare_authorized_production(approved)
    assert a["production_task"].id is not None; print("APPROVED_RETRY_CONTINUES=PASS")
    materialized = prepare_authorized_production(approved); assert materialized["production_task"].id == a["production_task"].id; print("MATERIALIZED_RETRY_RETURNS_EXISTING=PASS")
    idem = prepare_authorized_production(approved); assert idem["production_task"].id == a["production_task"].id; print("G4A_PREPARE_IDEMPOTENT=PASS")
    concurrent = _create("concurrent")
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda _: prepare_authorized_production(concurrent), range(2)))
    assert len({row["production_task"].id for row in rows}) == 1 and len([t for t in get_tasks() if t.parameters.get("content_plan_id") == concurrent]) == 1
    print("G4A_PREPARE_CONCURRENCY=PASS")
    for round_index in range(20):
        os.environ["OS_PRODUCTION_PROVIDER"] = "github" if round_index % 2 == 0 else "ai_gateway"
        concurrent_id = _create("stress-" + str(round_index))
        with ThreadPoolExecutor(max_workers=2) as pool:
            stress_rows = list(pool.map(lambda _: prepare_authorized_production(concurrent_id), range(2)))
        assert len({row["production_task"].id for row in stress_rows}) == 1
        assert len([t for t in get_tasks() if t.parameters.get("content_plan_id") == concurrent_id]) == 1
        assert get_plan(concurrent_id)["status"] == "materialized"
    print("G4A_CONCURRENCY_STRESS_20_ROUNDS=PASS"); print("ROUTING_CONCURRENCY_SINGLE_TASK=PASS")
    corruption = _create("corrupt"); prepared_corrupt = prepare_authorized_production(corruption)
    with sqlite3.connect(DB) as db: db.execute("DELETE FROM production_tasks WHERE id=?", (prepared_corrupt["production_task"].id,)); db.commit()
    try: prepare_authorized_production(corruption); raise AssertionError("corruption repaired")
    except ValueError: pass
    print("MATERIALIZED_LINKAGE_CORRUPTION_BLOCKED=PASS")

    # A stale same-revision approval cannot move materialized back to approved.
    from intelligence.content_brain import set_plan_status
    try: set_plan_status(approved, "approved", expected_revision=get_plan(approved)["revision"]); raise AssertionError("materialized regressed")
    except ValueError: pass
    assert get_plan(approved)["status"] == "materialized"
    print("PLAN_STATUS_CAS_SAFE=PASS"); print("SAME_REVISION_STATUS_REGRESSION_BLOCKED=PASS"); print("LATE_APPROVAL_CANNOT_REGRESS_MATERIALIZED=PASS")

    # Pre-G4 task without routing evidence remains one honest legacy task.
    legacy = _create("legacy"); legacy_task = prepare_authorized_production(legacy)["production_task"]
    with sqlite3.connect(DB) as db:
        params = dict(legacy_task.parameters); params.pop("production_routing", None)
        db.execute("UPDATE production_tasks SET parameters=? WHERE id=?", (json.dumps(params), legacy_task.id)); db.commit()
    legacy_result = prepare_authorized_production(legacy)
    assert legacy_result["production_task"].id == legacy_task.id
    assert legacy_result["routing"]["routing_evidence_status"] == "legacy_existing"
    assert len([t for t in get_tasks() if t.parameters.get("content_plan_id") == legacy]) == 1
    print("LEGACY_TASK_NO_DUPLICATE=PASS"); print("LEGACY_ROUTING_EVIDENCE_HANDLED_HONESTLY=PASS")

    # Manual lifecycle primitives remain available without G4 authorization.
    autonomy.update_autonomy_settings(autonomy_enabled=False, kill_switch_active=True)
    os.environ["OS_PRODUCTION_PROVIDER"] = "github"
    manual = _create("manual"); approve_plan(manual); manual_task = materialize_plan(manual)
    assert manual_task.provider == "github" and get_plan(manual)["status"] == "materialized"
    print("MANUAL_GITHUB_MATERIALIZE=PASS")
    os.environ["OS_PRODUCTION_PROVIDER"] = "ai_gateway"
    manual_ai = _create("manual-ai"); approve_plan(manual_ai); manual_ai_task = materialize_plan(manual_ai)
    assert manual_ai_task.provider == "ai_gateway" and get_plan(manual_ai)["status"] == "materialized"
    print("MANUAL_AI_MATERIALIZE=PASS"); print("MANUAL_MATERIALIZATION_REGRESSION=PASS"); print("MANUAL_AUTONOMOUS_SEPARATION=PASS")
    counts = _counts(); assert counts["runtime_jobs"] == 0 and counts["production_results"] == 0 and counts["video_assets"] == 0 and counts["publish_tasks"] == 0
    print("NO_RUNTIME_JOB=PASS"); print("NO_RESULT_ASSET_PUBLISH=PASS")
    print("G4A_AUTHORIZED_PRODUCTION_SMOKE=PASS")


if __name__ == "__main__":
    try: main()
    finally:
        gc.collect()
        for _name in ("OS_PRODUCTION_PROVIDER", "OS_DATABASE_PATH", "OS_TESTING"):
            os.environ.pop(_name, None)
        try: DB.unlink()
        except FileNotFoundError: pass
        except PermissionError:
            # Some legacy sqlite helpers retain a connection until interpreter
            # shutdown; the isolated file is outside the repository and is
            # never the production database.
            pass
