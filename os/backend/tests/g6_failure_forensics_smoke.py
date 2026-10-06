"""Isolated, network-free persistence contract for G6 generation failures."""
from test_database_helper import TEST_DATABASE_PATH

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.providers.text import TextProviderError
from intelligence import learning
from intelligence.content_brain import DeterministicContentPlanProvider


SECRET = 'SECRET_API_KEY_123 http://private-provider.example Bearer TOPSECRET'


class RaisingProvider:
    def __init__(self, error):
        self.error = error
        self.calls = 0

    def generate_content_plan(self, snapshot, context):
        self.calls += 1
        raise self.error


def fresh_snapshot():
    learning.init_learning()
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        sid = conn.execute('''INSERT INTO intelligence_feedback_snapshots
            (account_id,platform,content_id,snapshot_key,feedback_json,strategy_json,
             metrics_json,funnel_json,created_at)
            VALUES (1,'youtube','offline','offline-' || hex(randomblob(16)),
                    '{}','{}','{}','{}','2026-10-06T00:00:00+00:00')''').lastrowid
    return {'id': sid, 'content_id': 'offline', 'strategy': {},
            'metrics_snapshot': {'learning_evidence': {'fingerprint': f'{sid:064x}'}}}


def run(snapshot, provider):
    with patch.object(learning, 'prepare_feedback_snapshot', return_value=snapshot):
        return learning.run_feedback_cycle(1, 'youtube', '2026-08-13', '2026-09-09', provider=provider)


def state(sid):
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        return conn.execute('''SELECT learning_state,learning_plan_id,learning_reason
            FROM intelligence_feedback_snapshots WHERE id=?''', (sid,)).fetchone()


def main():
    cases = (
        ('DIRECTED_GENERATION_PARSE_ERROR', 'CONTENT_EXTRACTED'),
        ('DIRECTED_GENERATION_SCHEMA_ERROR', 'JSON_PARSED'),
        ('DIRECTED_GENERATION_SAFETY_REJECTED', 'SCHEMA_VALIDATED'),
        ('DIRECTED_GENERATION_CONTENT_PLAN_VALIDATION_ERROR', 'CONSTRAINTS_VALIDATED'),
    )
    for code, stage in cases:
        snapshot = fresh_snapshot()
        error = ValueError(SECRET)
        error.forensic_code = code
        error.forensic_stage = stage
        error.forensic_provider_returned = True
        provider = RaisingProvider(error)
        try:
            run(snapshot, provider)
        except ValueError as caught:
            assert caught is error
        else:
            raise AssertionError('generation failure was concealed')
        expected = f'FEEDBACK_GENERATION_FAILED|CODE={code}|STAGE={stage}|PROVIDER_RETURNED=true'
        assert state(snapshot['id']) == ('review', None, expected)
        assert SECRET not in expected
        assert run(snapshot, provider)['learning_state'] == 'review'
        assert provider.calls == 1

    snapshot = fresh_snapshot()
    provider = RaisingProvider(TextProviderError(SECRET))
    try:
        run(snapshot, provider)
    except TextProviderError:
        pass
    else:
        raise AssertionError('provider failure was concealed')
    assert state(snapshot['id']) == ('review', None,
        'FEEDBACK_GENERATION_FAILED|CODE=PROVIDER_FAILURE|STAGE=PROVIDER_REQUEST|PROVIDER_RETURNED=false')

    snapshot = fresh_snapshot()
    provider = RaisingProvider(RuntimeError(SECRET))
    try:
        run(snapshot, provider)
    except RuntimeError:
        pass
    else:
        raise AssertionError('unknown failure was concealed')
    assert state(snapshot['id']) == ('review', None, 'FEEDBACK_CYCLE_INTERRUPTED')

    snapshot = fresh_snapshot()
    result = run(snapshot, DeterministicContentPlanProvider())
    assert result['learning_state'] == 'completed' and result['learning_plan_id'] is not None
    assert state(snapshot['id']) == ('completed', result['learning_plan_id'], None)
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        rows = conn.execute('SELECT learning_reason FROM intelligence_feedback_snapshots').fetchall()
        assert all(SECRET not in str(row) for row in rows)
        assert conn.execute('SELECT COUNT(*) FROM intelligence_content_plans').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM intelligence_policy_decisions').fetchone()[0] == 1
    print('G6_FAILURE_FORENSICS=PASS')
    print('G6_SAFE_PROVIDER_CLASSIFICATION=PASS')
    print('G6_UNKNOWN_FALLBACK=PASS')
    print('G6_SUCCESS_AND_NO_RETRY=PASS')


if __name__ == '__main__':
    main()
