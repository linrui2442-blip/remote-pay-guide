"""Network-free, isolated proof of operator-only one-time G6 regeneration."""
from test_database_helper import TEST_DATABASE_PATH

import json
import sqlite3
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence import learning
from intelligence.content_brain import DeterministicContentPlanProvider, save_plan


SECRET = 'SECRET_API_KEY_123 Bearer TOPSECRET http://private-provider.example'


def snapshot(*, sid=None, state='review', reason='FEEDBACK_CYCLE_INTERRUPTED', plan_id=None):
    learning.init_learning()
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        fields = '''account_id,platform,content_id,snapshot_key,feedback_json,strategy_json,
            metrics_json,funnel_json,created_at,learning_state,learning_plan_id,learning_reason'''
        values = (1, 'youtube', 'offline', 'offline-' + uuid.uuid4().hex, '{}', '{}',
                  json.dumps({'learning_evidence': {'fingerprint': 'a' * 64}}), '{}',
                  '2026-10-06T00:00:00+00:00', state, plan_id, reason)
        if sid is None:
            sid = conn.execute(f'INSERT INTO intelligence_feedback_snapshots ({fields}) VALUES ({",".join("?" for _ in values)})', values).lastrowid
        else:
            conn.execute(f'INSERT INTO intelligence_feedback_snapshots (id,{fields}) VALUES (?,{",".join("?" for _ in values)})', (sid, *values))
    return sid


def read(sid):
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        return conn.execute('''SELECT learning_state,learning_plan_id,learning_reason
            FROM intelligence_feedback_snapshots WHERE id=?''', (sid,)).fetchone()


class CountingProvider:
    def __init__(self, error=None):
        self.error = error
        self.calls = 0
        self.lock = threading.Lock()

    def generate_content_plan(self, snap, context):
        with self.lock:
            self.calls += 1
        if self.error:
            raise self.error
        return DeterministicContentPlanProvider().generate_content_plan(snap, context)


def assert_rejected(sid, provider):
    before = provider.calls
    try:
        learning.recover_feedback_generation(sid, provider=provider)
    except ValueError as exc:
        assert str(exc) in ('FEEDBACK_RECOVERY_NOT_ELIGIBLE', 'FEEDBACK_RECOVERY_PLAN_EXISTS')
    else:
        raise AssertionError('ineligible recovery accepted')
    assert provider.calls == before


def main():
    # The legacy generic reason is admitted only for the manually reviewed #11.
    sid = snapshot(sid=11)
    provider = CountingProvider()
    result = learning.recover_feedback_generation(sid, provider=provider)
    assert provider.calls == 1 and result['learning_state'] == 'completed'
    assert read(sid) == ('completed', result['learning_plan_id'], 'RECOVERED_FROM|FEEDBACK_CYCLE_INTERRUPTED')
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        assert conn.execute('SELECT count(*) FROM intelligence_content_plans').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM intelligence_policy_decisions').fetchone()[0] == 1
    assert_rejected(sid, provider)

    previous = ('FEEDBACK_GENERATION_FAILED|CODE=DIRECTED_GENERATION_SCHEMA_ERROR|'
                'STAGE=JSON_PARSED|PROVIDER_RETURNED=true')
    sid = snapshot(reason=previous)
    error = ValueError(SECRET)
    error.forensic_code = 'DIRECTED_GENERATION_SAFETY_REJECTED'
    error.forensic_stage = 'SCHEMA_VALIDATED'
    error.forensic_provider_returned = True
    provider = CountingProvider(error)
    try:
        learning.recover_feedback_generation(sid, provider=provider)
    except ValueError as caught:
        assert caught is error
    else:
        raise AssertionError('recovery failure concealed')
    current = ('FEEDBACK_GENERATION_FAILED|CODE=DIRECTED_GENERATION_SAFETY_REJECTED|'
               'STAGE=SCHEMA_VALIDATED|PROVIDER_RETURNED=true')
    assert read(sid) == ('review', None, f'RECOVERY_FAILED|PREVIOUS={previous}|CURRENT={current}')
    assert SECRET not in read(sid)[2]
    assert_rejected(sid, provider)

    # Provider transport outcomes are not confirmed local validation failures.
    for reason in ('FEEDBACK_CYCLE_INTERRUPTED',
                   'FEEDBACK_GENERATION_FAILED|CODE=PROVIDER_FAILURE|STAGE=PROVIDER_REQUEST|PROVIDER_RETURNED=false',
                   'FEEDBACK_GENERATION_FAILED|CODE=DIRECTED_GENERATION_UNKNOWN_VALIDATION_ERROR|STAGE=PROVIDER_RETURNED|PROVIDER_RETURNED=true'):
        sid = snapshot(reason=reason)
        assert_rejected(sid, CountingProvider())
    for state in ('generating', 'completed'):
        sid = snapshot(state=state, reason=previous)
        assert_rejected(sid, CountingProvider())
    sid = snapshot(reason=previous, plan_id=123)
    assert_rejected(sid, CountingProvider())
    sid = snapshot(reason=previous)
    snap = learning.bridge.get_feedback_snapshot(sid)
    saved = save_plan(DeterministicContentPlanProvider().generate_content_plan(snap, {}), sid)
    assert saved['id'] and read(sid)[1] is None
    assert_rejected(sid, CountingProvider())

    # Ordinary G6 keeps its original NULL-only claim and cannot reclaim review.
    sid = snapshot(reason=previous)
    provider = CountingProvider()
    with patch.object(learning, 'prepare_feedback_snapshot', return_value=learning.bridge.get_feedback_snapshot(sid)):
        assert learning.run_feedback_cycle(1, 'youtube', '2026-08-13', '2026-09-09', provider=provider)['learning_state'] == 'review'
    assert provider.calls == 0

    # Twenty fresh snapshots, four racing callers each: exactly one wins.
    for _ in range(20):
        sid = snapshot(reason=previous)
        provider = CountingProvider()
        def attempt(_):
            try:
                return learning.recover_feedback_generation(sid, provider=provider)
            except ValueError as exc:
                assert str(exc) in ('FEEDBACK_RECOVERY_NOT_ELIGIBLE', 'FEEDBACK_RECOVERY_CLAIM_LOST')
                return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(attempt, range(4)))
        assert provider.calls == 1 and sum(x is not None for x in outcomes) == 1
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            assert conn.execute('SELECT count(*) FROM intelligence_content_plans WHERE source_snapshot_id=?', (sid,)).fetchone()[0] == 1
            plan_id = read(sid)[1]
            assert conn.execute('SELECT count(*) FROM intelligence_policy_decisions WHERE content_plan_id=?', (plan_id,)).fetchone()[0] == 1

    # A fresh normal cycle still uses the original path.
    sid = snapshot(state=None, reason=None)
    provider = CountingProvider()
    with patch.object(learning, 'prepare_feedback_snapshot', return_value=learning.bridge.get_feedback_snapshot(sid)):
        assert learning.run_feedback_cycle(1, 'youtube', '2026-08-13', '2026-09-09', provider=provider)['learning_state'] == 'completed'
    assert provider.calls == 1
    print('G6_EXPLICIT_LEGACY_RECOVERY=PASS')
    print('G6_RECOVERY_FAILURE_HISTORY=PASS')
    print('G6_RECOVERY_INELIGIBLE_STATES=PASS')
    print('G6_RECOVERY_CONCURRENCY_20X4=PASS')
    print('G6_NORMAL_CLAIM_UNCHANGED=PASS')


if __name__ == '__main__':
    main()
