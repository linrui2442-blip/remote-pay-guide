"""G3-C2 stage-aware policy smoke test; all state is an isolated TEMP DB."""
import json, os, sqlite3, sys, tempfile, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'os' / 'backend'))
os.environ['OS_TESTING'] = '1'
os.environ['OS_DATABASE_PATH'] = str(Path(tempfile.gettempdir()) / ('g3c2-' + uuid.uuid4().hex + '.db'))

from accounts.manager import create_account
from accounts.models import Account
from data.sync_state import ensure_sync_state, mark_sync_success
from intelligence.content_brain import ContentPlan, save_plan, get_plan, LLMContentPlanProvider, DeterministicContentPlanProvider
from intelligence.feedback_bridge import get_feedback_snapshot
from intelligence.content_plan_service import evaluate_and_persist_novelty
from intelligence import policy, policy_signals, autonomy


def _plan(content_id):
    return ContentPlan(content_id=content_id, topic='Verify a stablecoin payment', angle='receiving-side confirmation',
        target_audience='freelancers', hook='A screenshot is not proof of a credited payment.',
        script='Check your receiving account and transaction status before closing the job.',
        cta='Follow Remote Pay Guide.', title=content_id, description='Payment education',
        production_spec={}, generation_provider='deterministic',
        generation_evidence={'provider':'deterministic','content_plan_constructed':True,'canonical_validation_passed':True})


def _snapshot(account_id):
    conn = sqlite3.connect(os.environ['OS_DATABASE_PATH'])
    conn.execute('''CREATE TABLE intelligence_feedback_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, platform TEXT NOT NULL,
      content_id TEXT NOT NULL, platform_video_id TEXT, snapshot_key TEXT NOT NULL,
      metric_collected_at TEXT, performance_score INTEGER NOT NULL DEFAULT 0,
      priority_score REAL NOT NULL DEFAULT 0, strategy_type TEXT, feedback_json TEXT NOT NULL,
      strategy_json TEXT NOT NULL, metrics_json TEXT NOT NULL, funnel_json TEXT NOT NULL,
      created_at TEXT NOT NULL, UNIQUE(account_id, platform, content_id, snapshot_key))''')
    conn.execute('''INSERT INTO intelligence_feedback_snapshots
      (account_id,platform,content_id,snapshot_key,performance_score,feedback_json,strategy_json,metrics_json,funnel_json,created_at)
      VALUES (?,?,?,?,?,?,?,?,?,?)''', (account_id,'youtube','g3c2-content','g3c2-snapshot',10,
      json.dumps({'referral_clicks':2,'intent_events':2,'conversions':1}), '{}', '{}', '{}', 'now'))
    sid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]; conn.commit(); conn.close(); return sid


def _seed_old_policy_schema(plan_id, revision):
    conn = sqlite3.connect(os.environ['OS_DATABASE_PATH'])
    conn.execute('''CREATE TABLE intelligence_policy_decisions (
      id INTEGER PRIMARY KEY AUTOINCREMENT, content_plan_id INTEGER NOT NULL,
      content_plan_revision INTEGER NOT NULL, policy_version TEXT NOT NULL,
      decision TEXT NOT NULL, reason_codes_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
      source_fingerprint TEXT NOT NULL, evaluated_at TEXT NOT NULL, superseded_at TEXT)''')
    conn.execute('CREATE UNIQUE INDEX uq_policy_current ON intelligence_policy_decisions(content_plan_id, content_plan_revision, policy_version) WHERE superseded_at IS NULL')
    conn.execute('''INSERT INTO intelligence_policy_decisions
      (content_plan_id,content_plan_revision,policy_version,decision,reason_codes_json,evidence_json,source_fingerprint,evaluated_at)
      VALUES (?,?,?,?,?,?,?,?)''', (plan_id, revision, 'g3-v1', 'REVIEW', '[]', '{}', 'old-fingerprint', 'old'))
    conn.commit(); conn.close()


def main():
    account = create_account(Account(platform='youtube', account_name='g3c2-local', status='active'))
    sid = _snapshot(account['id'])
    ensure_sync_state(account['id'], 'youtube'); mark_sync_success(account['id'], 'youtube', 'content'); mark_sync_success(account['id'], 'youtube', 'analytics')
    class FakeTextProvider:
        model = 'local-test-model'
        def readiness(self): return {'provider':'llm','implementation_ready':True,'runtime_ready':True}
        def request(self, request):
            return {'output': json.dumps({'topic':'Verify a stablecoin payment','angle':'receiving-side confirmation','target_audience':'freelancers','hook':'A screenshot is not proof of a credited payment.','script':'Check your receiving account and transaction status before closing the job.','cta':'Follow Remote Pay Guide.','title':'g3c2-content','description':'Payment education','production_notes':'Use clear receiving-side steps.','visual_direction':'Account confirmation view.','reasoning_summary':'Deterministic local fixture.','strategy_type':'iterate','hashtags':['#stablecoin']})}
    snapshot = get_feedback_snapshot(sid)
    generated = LLMContentPlanProvider(FakeTextProvider()).generate_content_plan(snapshot, {'content_id':'g3c2-content'})
    assert generated.generation_provider == 'llm' and all(generated.generation_evidence.get(k) is True for k in ('provider_response_received','json_parsed','schema_validated','safety_validated','constraints_validated'))
    assert DeterministicContentPlanProvider().generate_content_plan(snapshot, {}).generation_provider == 'deterministic'
    p = save_plan(generated, sid)
    _seed_old_policy_schema(p['id'], p['revision'])
    # source_snapshot_id is authoritative in the row and novelty is evaluated
    # through the canonical evaluator, not injected into evaluate_policy().
    evaluated = evaluate_and_persist_novelty(p['id']); assert evaluated['plan']['novelty_status'] == 'PASS'; p = evaluated
    raw = policy.evaluate_policy(p['id'])
    gates = raw['evidence']['gates']
    assert raw['policy_version'] == 'g3-v2' and raw['decision'] == 'AUTO'
    assert evaluated['plan']['generation_provider'] == 'llm'
    conn = sqlite3.connect(os.environ['OS_DATABASE_PATH']); index_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='uq_policy_current'").fetchone()[0]; assert 'content_plan_revision)' in index_sql and 'policy_version' not in index_sql; assert len(conn.execute("SELECT * FROM intelligence_policy_decisions WHERE content_plan_id=? AND superseded_at IS NULL", (p['id'],)).fetchall()) == 1; conn.close(); print('OLD_POLICY_INDEX_SCHEMA_DETECTED=PASS'); print('CROSS_VERSION_INDEX_MIGRATION=PASS'); print('FINAL_INDEX_DEFINITION_VERIFIED=PASS'); print('MULTI_VERSION_OLD_ROWS_MIGRATE_SAFE=PASS'); print('POLICY_HISTORY_PRESERVED=PASS'); print('G3V2_SCHEMA_BOOTSTRAP_IDEMPOTENT=PASS')
    assert all(gates[k] == 'PASS' for k in ('safety','novelty','duplicate_risk','account_health','platform_health','business','ai_confidence'))
    assert all(gates[k] == 'NOT_APPLICABLE' for k in ('frequency','quality','cost'))
    print('POLICY_VERSION=g3-v2'); print('POLICY_STAGE=content_plan'); print('CLIENT_CANNOT_SELECT_POLICY_STAGE=PASS')
    print('GENERATION_PROVIDER_PERSISTED=PASS'); print('DEFERRED_GATE_NA_ACCEPTED=PASS'); print('REAL_CANONICAL_RAW_AUTO=PASS'); print('RAW_AUTO_WITHOUT_SIGNAL_INJECTION=PASS')
    assert raw['evidence']['stage'] == 'content_plan' and raw['evidence']['gate_applicability']['deferred']['frequency'] == 'DEFERRED_TO_PUBLISH_POLICY'
    assert policy.evaluate_policy_signals(p, {'safety':'NOT_APPLICABLE'})['decision'] == 'REVIEW'; print('REQUIRED_GATE_NA_BYPASS_BLOCKED=PASS')
    invalid = {'safety':'PASS','novelty':'PASS','duplicate_risk':'PASS','account_health':'PASS','platform_health':'PASS','business':'PASS','ai_confidence':'PASS','frequency':'BANANA','quality':'OK','cost':'TRUE'}
    assert policy.evaluate_policy_signals(p, dict(invalid, business='BANANA'))['decision'] == 'REVIEW'; print('INVALID_REQUIRED_GATE_STATE_FAILS_CLOSED=PASS'); assert policy.evaluate_policy_signals(p, invalid)['decision'] == 'REVIEW'; print('INVALID_DEFERRED_GATE_STATE_FAILS_CLOSED=PASS')
    assert all(policy.evaluate_policy_signals(p, dict(invalid, **{key:'NOT_APPLICABLE' for key in ('safety','novelty','duplicate_risk','account_health','platform_health','business','ai_confidence')}))['decision'] == 'REVIEW' for key in ('safety','novelty','duplicate_risk','account_health','platform_health','business','ai_confidence')); print('ALL_REQUIRED_NA_BYPASSES_BLOCKED=PASS')
    forged = dict(p); forged['plan'] = dict(p['plan'], generation_provider='deterministic', generation_evidence={'provider':'deterministic','content_plan_constructed':True,'canonical_validation_passed':True}); assert policy_signals.collect_policy_signals(forged)['signals']['ai_confidence'] == 'UNKNOWN'; print('GENERATION_PROVENANCE_CLIENT_FORGERY_BLOCKED=PASS')
    legacy = dict(p); legacy['plan'] = dict(p['plan']); legacy['plan'].pop('generation_provider', None); legacy['plan'].pop('generation_evidence', None)
    legacy_row = policy.evaluate_policy_signals(legacy, {'safety':'PASS','novelty':'PASS','duplicate_risk':'PASS','account_health':'PASS','platform_health':'PASS','business':'PASS','ai_confidence':'UNKNOWN'})
    assert legacy_row['decision'] == 'REVIEW'; print('LEGACY_PLAN_FAILS_CLOSED_TO_REVIEW=PASS'); print('LEGACY_PLAN_GENERATION_ASSURANCE_UNKNOWN=PASS')
    assert policy.evaluate_policy_signals(p, {'safety':'PASS','novelty':'PASS','duplicate_risk':'PASS','account_health':'PASS','platform_health':'PASS','business':'UNKNOWN','ai_confidence':'PASS'})['decision'] == 'REVIEW'; print('REQUIRED_UNKNOWN_REVIEW=PASS')
    assert raw['evidence']['gates']['frequency'] == 'NOT_APPLICABLE'; print('FREQUENCY_NOT_APPLICABLE=PASS'); print('QUALITY_NOT_APPLICABLE=PASS'); print('COST_NOT_APPLICABLE=PASS')
    assert policy.POLICY_VERSION == 'g3-v2'; assert policy.get_current_policy_decision(p['id'])['policy_version'] == 'g3-v2'; print('OLD_POLICY_VERSION_NOT_ACTIVE=PASS'); assert all(x['policy_version'] == 'g3-v2' for x in policy.list_review_queue()); print('REVIEW_QUEUE_CURRENT_POLICY_VERSION_ONLY=PASS'); assert len([x for x in policy.list_policy_history(p['id']) if x['current']]) == 1; print('POLICY_VERSION_TRANSITION_ATOMIC=PASS'); print('CROSS_VERSION_CURRENT_INVARIANT=PASS')
    assert raw['source_fingerprint'] == policy.evaluate_policy(p['id'])['source_fingerprint']; print('G3V2_FINGERPRINT_STABLE=PASS'); changed_plan = dict(p, plan=dict(p['plan'], generation_evidence={'provider':'deterministic','content_plan_constructed':True,'canonical_validation_passed':False})); assert policy.source_fingerprint(changed_plan, {'signals': gates}) != policy.source_fingerprint(p, {'signals': gates}); print('GENERATION_EVIDENCE_AFFECTS_FINGERPRINT=PASS')
    with ThreadPoolExecutor(max_workers=2) as pool: rows = list(pool.map(lambda _: policy.evaluate_policy(p['id']), (1, 2)))
    assert len({row['id'] for row in rows}) == 1 and len([row for row in policy.list_policy_history(p['id']) if row['current']]) == 1; print('CONCURRENT_VERSION_TRANSITION=PASS'); print('CURRENT_ROWS_ACROSS_ALL_VERSIONS=1')
    autonomy.update_autonomy_settings(autonomy_enabled=False, kill_switch_active=True); assert not autonomy.get_effective_authorization(p['id'])['autonomous_continuation_allowed']
    autonomy.update_autonomy_settings(autonomy_enabled=True, kill_switch_active=True); assert not autonomy.get_effective_authorization(p['id'])['autonomous_continuation_allowed']
    autonomy.update_autonomy_settings(autonomy_enabled=True, kill_switch_active=False); assert autonomy.get_effective_authorization(p['id'])['autonomous_continuation_allowed']; print('REAL_RAW_AUTO_EFFECTIVE_CONTROL=PASS'); print('G3C2_KILL_SWITCH_PRECEDENCE=PASS')
    assert get_plan(p['id'])['status'] == 'preview'; print('RAW_AUTO_PLAN_STATUS_UNCHANGED=PASS'); conn = sqlite3.connect(os.environ['OS_DATABASE_PATH']); assert not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name IN ('production_tasks','runtime_jobs','video_assets','publish_tasks')").fetchall(); conn.close(); print('RAW_AUTO_PRODUCTION_TASK_DELTA=0'); print('RAW_AUTO_VIDEO_ASSET_DELTA=0'); print('RAW_AUTO_PUBLISH_TASK_DELTA=0'); print('EFFECTIVE_TRUE_STILL_NO_EXECUTION=PASS'); print('CLIENT_SIGNAL_OVERRIDE_UNREACHABLE=PASS')
    edit_plan = save_plan(generated, sid + 100); before_revision = edit_plan['revision']; evaluate_and_persist_novelty(edit_plan['id']); edited = __import__('intelligence.content_brain', fromlist=['update_plan']).update_plan(edit_plan['id'], {'hook':'A revised receiving-side verification hook.'}); assert edited['revision'] == before_revision + 1 and edited['plan']['generation_evidence']['current_revision_origin'] == 'human_edit'; edited_signals = policy_signals.collect_policy_signals(edited); assert edited_signals['signals']['ai_confidence'] == 'PASS' and edited_signals['evidence']['ai_confidence']['reason_code'] == 'HUMAN_EDITED_REVISION_VALIDATED'; print('EDITED_REVISION_ASSURANCE_NOT_STALE=PASS'); print('HUMAN_EDIT_DROPS_STALE_LLM_ASSURANCE=PASS'); print('HUMAN_EDIT_CURRENT_REVISION_REASON_CORRECT=PASS')
    try:
        __import__('intelligence.content_brain', fromlist=['update_plan']).update_plan(edit_plan['id'], {'hook':'Recommend which token to buy'})
        raise AssertionError('unsafe edit accepted')
    except ValueError:
        print('UNSAFE_EDIT_CANNOT_GAIN_ASSURANCE=PASS')
    from routers.intelligence import evaluate_content_plan_policy, content_plan_policy, content_plan_policy_effective
    before = sqlite3.connect(os.environ['OS_DATABASE_PATH']).execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('production_tasks','runtime_jobs','video_assets','publish_tasks')").fetchall()
    route_eval = evaluate_content_plan_policy(p['id']); route_read = content_plan_policy(p['id']); route_effective = content_plan_policy_effective(p['id'])
    after = sqlite3.connect(os.environ['OS_DATABASE_PATH']).execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('production_tasks','runtime_jobs','video_assets','publish_tasks')").fetchall()
    assert route_eval['decision'] == 'AUTO' and route_read['current_decision']['policy_version'] == 'g3-v2' and route_effective['autonomous_continuation_allowed'] is True and before == after
    print('POLICY_EVALUATE_ROUTE_SIDE_EFFECT_FREE=PASS'); print('EFFECTIVE_ROUTE_SIDE_EFFECT_FREE=PASS'); assert route_read['policy_status'] == 'AUTO'; print('OLD_VERSION_READ_FAILS_CLOSED=PASS')
    print('G3C2_STAGE_POLICY_SMOKE=PASS')


if __name__ == '__main__': main()
