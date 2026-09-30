"""Network-free canonical learning proof, with persisted analytics."""
from test_database_helper import TEST_DATABASE_PATH
import sys
import sqlite3
import socket
import json
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from accounts.manager import create_account
from accounts.models import Account
from analytics.manager import save_metric
from analytics.models import AnalyticsMetric
from intelligence.learning import run_feedback_cycle, recover_feedback_policy
from intelligence.content_brain import DeterministicContentPlanProvider, get_plan
from intelligence.policy import get_current_policy_decision


def main():
    account = create_account(Account(platform='youtube', account_name='offline', status='connected'))
    now = datetime(2026, 9, 30, tzinfo=timezone.utc)
    provider = DeterministicContentPlanProvider()
    def cycle():
        return run_feedback_cycle(account['id'], 'youtube', '2026-09-01', '2026-09-20', provider=provider, now=now)
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        try:
            cycle()
        except ValueError as e:
            assert str(e) == 'NO_MATURE_CANONICAL_COHORT'
        else:
            raise AssertionError('empty cohort accepted')
        save_metric(AnalyticsMetric(video_id='unknown', platform='youtube', account_id=account['id'], views=20, period_start='2026-09-01', period_end='2026-09-20'))
        try:
            cycle()
        except ValueError as e:
            assert str(e) == 'NO_MATURE_CANONICAL_COHORT'
        else:
            raise AssertionError('fallback identity accepted')
        for turn in range(20):
            save_metric(AnalyticsMetric(video_id='platform-id', content_id='short-test', platform='youtube', account_id=account['id'], source='offline', views=100+turn, period_start='2026-09-01', period_end='2026-09-20'))
            with ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(lambda _: cycle(), range(4)))
            assert len({r['id'] for r in rows}) == 1
            final = cycle()
            assert final['learning_state'] == 'completed'
            plan = get_plan(final['learning_plan_id'])
            assert plan['status'] == 'preview' and plan['approved_revision'] is None
            assert plan['source_snapshot_id'] == final['id']
            assert get_current_policy_decision(plan['id'])['decision'] in {'AUTO', 'REVIEW', 'BLOCK'}
            assert recover_feedback_policy(final['id']) == final
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            assert conn.execute('SELECT COUNT(*) FROM intelligence_feedback_snapshots').fetchone()[0] == 20
            assert conn.execute('SELECT COUNT(*) FROM intelligence_content_plans').fetchone()[0] == 20
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ('production_tasks', 'publish_tasks'):
                if table in tables:
                    assert conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
        conn.close()
        save_metric(AnalyticsMetric(video_id='platform-id', content_id='short-test', platform='youtube', account_id=account['id'], source='offline', views=999, period_start='2026-09-01', period_end='2026-09-20'))
        with patch.object(provider, 'generate_content_plan', side_effect=RuntimeError('offline injected failure')) as generate:
            try:
                cycle()
            except RuntimeError:
                pass
            else:
                raise AssertionError('generation failure concealed')
            failed = cycle()
            assert failed['learning_state'] == 'review' and generate.call_count == 1
            assert recover_feedback_policy(failed['id'])['learning_state'] == 'review'
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            evidence = json.loads(conn.execute('SELECT metrics_json FROM intelligence_feedback_snapshots WHERE id=?', (failed['id'],)).fetchone()[0])['learning_evidence']
            assert evidence['sample_size'] == 1 and evidence['content_ids'] == ['short-test']
            assert evidence['window'] == ['2026-09-01', '2026-09-20']
            assert evidence['account_id'] == account['id'] and len(evidence['fingerprint']) == 64
        conn.close()
        try:
            run_feedback_cycle(account['id'], 'youtube', '2026-09-01', '2026-09-30', provider=provider, now=now)
        except ValueError as e:
            assert str(e) == 'MATURE_ANALYTICS_WINDOW_REQUIRED'
        else:
            raise AssertionError('immature cohort accepted')
    print('G6_CANONICAL_CHAIN=PASS')
    print('G6_IDENTITY_AND_MATURITY=PASS')
    print('G6_CONCURRENCY_20X4=PASS')
    print('G6_NO_PRODUCTION_OR_PUBLISH=PASS')
    print('G6_FAILURE_NO_GENERATION_RETRY=PASS')
    print('G6_EVIDENCE_WINDOW_FINGERPRINT=PASS')


if __name__ == '__main__':
    main()
