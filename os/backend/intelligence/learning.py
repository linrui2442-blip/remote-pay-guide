"""Persisted analytics -> existing FeedbackSnapshot -> preview -> policy.

No sync/provider execution is implicit. Analytics ingestion remains owned by
existing integrations. A failed generation claim is never automatically retried.
"""
import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta, timezone

from accounts.manager import get_account
from analytics.manager import get_metrics
from data.database_path import database_path
from data.growth import get_content_funnel
from data.query import query_data_center
from intelligence import feedback_bridge as bridge
from intelligence.content_brain import select_content_plan_provider, save_plan, get_plan
from intelligence.feedback import analyze_feedback
from intelligence.strategy import build_production_strategy
from intelligence.policy import evaluate_policy
from ai.providers.text import TextProviderError


_GENERATION_FORENSIC_CODES = frozenset({
    'DIRECTED_GENERATION_PARSE_ERROR',
    'DIRECTED_GENERATION_SCHEMA_ERROR',
    'DIRECTED_GENERATION_SAFETY_REJECTED',
    'DIRECTED_GENERATION_MUST_INCLUDE_REJECTED',
    'DIRECTED_GENERATION_MUST_AVOID_REJECTED',
    'DIRECTED_GENERATION_CONTENT_PLAN_VALIDATION_ERROR',
    'DIRECTED_GENERATION_UNKNOWN_VALIDATION_ERROR',
})
_GENERATION_FORENSIC_STAGES = frozenset({
    'PROVIDER_RETURNED', 'CONTENT_EXTRACTED', 'JSON_PARSED',
    'SCHEMA_VALIDATED', 'SAFETY_VALIDATED', 'CONSTRAINTS_VALIDATED',
})


def _generation_failure_reason(exc):
    """Persist fixed taxonomy only, never exception text or provider output."""
    code = getattr(exc, 'forensic_code', None)
    stage = getattr(exc, 'forensic_stage', None)
    returned = getattr(exc, 'forensic_provider_returned', None)
    if (type(code) is str and code in _GENERATION_FORENSIC_CODES
            and type(stage) is str and stage in _GENERATION_FORENSIC_STAGES
            and type(returned) is bool):
        return f'FEEDBACK_GENERATION_FAILED|CODE={code}|STAGE={stage}|PROVIDER_RETURNED={str(returned).lower()}'
    if isinstance(exc, TextProviderError):
        return 'FEEDBACK_GENERATION_FAILED|CODE=PROVIDER_FAILURE|STAGE=PROVIDER_REQUEST|PROVIDER_RETURNED=false'
    return 'FEEDBACK_CYCLE_INTERRUPTED'


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


@contextmanager
def _db():
    with closing(sqlite3.connect(database_path(), timeout=30)) as conn:
        conn.row_factory = sqlite3.Row
        with conn:
            yield conn


def init_learning():
    bridge._ensure_table()
    with _db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        columns = {r['name'] for r in conn.execute('PRAGMA table_info(intelligence_feedback_snapshots)')}
        for name, kind in {'learning_state': 'TEXT', 'learning_plan_id': 'INTEGER',
                           'learning_reason': 'TEXT', 'learning_updated_at': 'TEXT'}.items():
            if name not in columns:
                conn.execute(f'ALTER TABLE intelligence_feedback_snapshots ADD COLUMN {name} {kind}')


def _state(snapshot_id):
    with _db() as conn:
        row = conn.execute('SELECT id,learning_state,learning_plan_id,learning_reason FROM intelligence_feedback_snapshots WHERE id=?', (snapshot_id,)).fetchone()
        return dict(row)


def _advance(snapshot_id, state, plan_id=None, reason=None):
    with _db() as conn:
        conn.execute('UPDATE intelligence_feedback_snapshots SET learning_state=?, learning_plan_id=COALESCE(?,learning_plan_id),learning_reason=?,learning_updated_at=? WHERE id=?',
                     (state, plan_id, reason, datetime.now(timezone.utc).isoformat(), snapshot_id))


def prepare_feedback_snapshot(account_id, platform, start_date, end_date, *, now=None):
    """Persist one strict snapshot, without a generation claim or provider call.

    Maturity means a complete analytics window ending >=48h before UTC today.
    """
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    today = (now or datetime.now(timezone.utc)).date()
    if start > end or end > today - timedelta(days=2):
        raise ValueError('MATURE_ANALYTICS_WINDOW_REQUIRED')
    account = get_account(account_id)
    if not account or account.get('platform') != platform:
        raise ValueError('ACCOUNT_PLATFORM_MISMATCH')
    # Never accept Query Center's legacy platform-video-id fallback as identity.
    raw = [r for r in get_metrics() if r.get('account_id') == account_id and r.get('platform') == platform]
    identities = {}
    for r in raw:
        if r.get('period_start') and r.get('period_end') and start_date <= r['period_start'] <= r['period_end'] <= end_date:
            identities.setdefault(r['video_id'], set()).add(r.get('content_id'))
    view = query_data_center(account_id=account_id, platform=platform, scope='active',
                             start_date=start_date, end_date=end_date, limit=1000)
    if view['total_matching'] > view['returned']:
        raise ValueError('COHORT_TRUNCATED_REVIEW_REQUIRED')
    rows = []
    for row in view['rows']:
        identity = identities.get(row['platform_video_id'], set())
        if (not row.get('content_id') or identity != {row['content_id']}
                or row['content_id'] == row['platform_video_id']):
            continue
        rows.append(row)
    if not rows:
        raise ValueError('NO_MATURE_CANONICAL_COHORT')
    rows.sort(key=lambda r: (r['content_id'], r['platform_video_id']))
    keys = ('content_id', 'platform_video_id', 'views', 'likes', 'comments', 'shares', 'watch_time', 'period_start', 'period_end')
    evidence_rows = [{k: r.get(k) for k in keys} for r in rows]
    # Funnel identity is also account/platform and time-window scoped.
    funnels = {cid: get_content_funnel(cid, start_date, end_date, platform=platform, account_id=account_id)
               for cid in sorted({r['content_id'] for r in rows})}
    # Legacy funnel traffic is lifetime/latest and not window/account scoped.
    # Window traffic is already in Data Center rows; never fingerprint lifetime
    # traffic or let another account's metrics alter this observation.
    funnels = {cid: {k: value[k] for k in ('intent', 'conversion')}
               for cid, value in funnels.items()}
    evidence = {'window': [start_date, end_date], 'content_ids': sorted(funnels),
                'account_id': account_id, 'platform': platform, 'sample_size': len(funnels),
                'metric_source': 'persisted_data_center', 'metrics': evidence_rows,
                'funnels': funnels, 'reason_codes': ['OBSERVED_PERFORMANCE_ONLY', 'NO_CAUSAL_INFERENCE']}
    fingerprint = hashlib.sha256(_json(evidence).encode()).hexdigest()
    evidence['fingerprint'] = fingerprint
    totals = {k: sum(r.get(k) or 0 for r in rows) for k in ('views', 'likes', 'comments', 'shares', 'watch_time')}
    funnel = {'intent': {'total': 0, 'by_type': {}}, 'conversion': {'total': 0, 'value': 0}}
    for item in funnels.values():
        intent, conversion = item.get('intent', {}), item.get('conversion', {})
        funnel['intent']['total'] += intent.get('total', 0)
        for key, value in intent.get('by_type', {}).items():
            funnel['intent']['by_type'][key] = funnel['intent']['by_type'].get(key, 0) + value
        for key in ('total', 'value'):
            funnel['conversion'][key] += conversion.get(key, 0)
    row = dict(totals, content_id=rows[0]['content_id'], platform_video_id=rows[0]['platform_video_id'],
               period_start=start_date, period_end=end_date, learning_evidence=evidence)
    feedback = analyze_feedback({'video_id': row['content_id'], 'performance': totals, 'funnel': funnel})
    strategy = build_production_strategy(feedback)
    # Preserve legacy strategy type; replace causal language for this observation.
    feedback.recommendations = ['Test one variable in a controlled follow-up; observed association is not causation.']
    strategy.objective = 'Test a controlled follow-up using observed cohort evidence'
    strategy.topic_direction = 'Observed performance suggests a hypothesis, not a proven causal effect'
    strategy.reasoning_summary = 'Observational evidence only; no causal attribution to creative variables.'
    strategy.parameters['recommendations'] = feedback.recommendations
    init_learning()
    try:
        snapshot = bridge._save_snapshot(account_id, platform, row, funnel, feedback, strategy)
    except sqlite3.IntegrityError:
        with _db() as conn:
            existing = conn.execute('SELECT id FROM intelligence_feedback_snapshots WHERE account_id=? AND platform=? AND content_id=? AND snapshot_key=?',
                                    (account_id, platform, row['content_id'], bridge._snapshot_key(row, funnel))).fetchone()
        if not existing:
            raise
        snapshot = bridge.get_feedback_snapshot(existing['id'])
    return snapshot


def run_feedback_cycle(account_id, platform, start_date, end_date, *, provider=None, now=None):
    """Prepare strict evidence, then retain the existing generation claim boundary."""
    snapshot = prepare_feedback_snapshot(account_id, platform, start_date, end_date, now=now)
    fingerprint = snapshot['metrics_snapshot']['learning_evidence']['fingerprint']
    sid = snapshot['id']
    with _db() as conn:
        won = conn.execute("UPDATE intelligence_feedback_snapshots SET learning_state='generating',learning_updated_at=? WHERE id=? AND learning_state IS NULL",
                           (datetime.now(timezone.utc).isoformat(), sid)).rowcount == 1
    if not won:
        return _state(sid)
    try:
        plan = (provider or select_content_plan_provider()).generate_content_plan(snapshot, {'strategy': snapshot['strategy'], 'content_id': 'feedback-' + fingerprint[:20]})
        plan.content_id = 'feedback-' + fingerprint[:20]
        plan.source_snapshot_id = sid
        plan.source_content_id = snapshot['content_id']
        saved = save_plan(plan, sid)
        _advance(sid, 'policy_pending', saved['id'])
        evaluate_policy(saved['id'])
        _advance(sid, 'completed', saved['id'])
    except Exception as exc:
        _advance(sid, 'review', reason=_generation_failure_reason(exc))
        raise
    return _state(sid)


def recover_feedback_policy(snapshot_id):
    """Read/local policy only; never repeat provider generation after a crash."""
    state = _state(snapshot_id)
    if state['learning_state'] == 'completed':
        return state
    pid = state['learning_plan_id']
    if not pid or not get_plan(pid) or get_plan(pid)['source_snapshot_id'] != snapshot_id:
        _advance(snapshot_id, 'review', reason='GENERATION_OUTCOME_UNKNOWN')
    else:
        evaluate_policy(pid)
        _advance(snapshot_id, 'completed', pid)
    return _state(snapshot_id)
