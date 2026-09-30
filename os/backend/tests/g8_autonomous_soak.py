"""Accelerated OFFLINE harness. Never an alternative production scheduler.

Every subprocess starts from disk, with socket writes disabled. Production and
publishing counts are zero; this does not certify a 72-hour live soak.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'os/backend'))


def step(mode, tick=0):
    assert os.environ.get('OS_TESTING') == '1'
    from data.database_path import assert_safe_test_database_path
    assert_safe_test_database_path(Path(os.environ['OS_DATABASE_PATH']))
    socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError('NETWORK_FORBIDDEN'))
    from intelligence.learning import init_learning, run_feedback_cycle
    from intelligence.content_brain import DeterministicContentPlanProvider
    from accounts.manager import create_account
    from accounts.models import Account
    from analytics.manager import save_metric
    from analytics.models import AnalyticsMetric
    from datetime import datetime, timezone
    from production.runtime.health import runtime_health
    if mode == '--seed':
        account = create_account(Account(platform='youtube', account_name='soak-fake', status='connected'))
        assert account['id'] == 1
        init_learning()
        return
    save_metric(AnalyticsMetric(video_id='soak-platform-id', content_id='soak-content', platform='youtube', account_id=1,
        source='offline-soak-fixture', views=100+tick, period_start='2026-09-01', period_end='2026-09-20'))
    provider = DeterministicContentPlanProvider()
    if tick % 5 == 0:
        def failure(*a, **k):
            raise RuntimeError('OFFLINE_FAILURE_INJECTION')
        provider.generate_content_plan = failure
    try:
        result = run_feedback_cycle(1, 'youtube', '2026-09-01', '2026-09-20', provider=provider,
                                    now=datetime(2026, 9, 30, tzinfo=timezone.utc))
    except RuntimeError as exc:
        assert str(exc) == 'OFFLINE_FAILURE_INJECTION'
        result = run_feedback_cycle(1, 'youtube', '2026-09-01', '2026-09-20', provider=provider,
                                    now=datetime(2026, 9, 30, tzinfo=timezone.utc))
        assert result['learning_state'] == 'review'
    report = runtime_health()
    assert report['entity_counts']['runtime_jobs'] in (None, 0)
    assert report['entity_counts']['publish_tasks'] in (None, 0)
    assert not any(report['duplicate_groups'].values())
    print(json.dumps({'cycle': result, 'metrics': report}))


def main():
    with tempfile.TemporaryDirectory(prefix='g8-offline-soak-') as folder:
        env = dict(os.environ, OS_TESTING='1', OS_DATABASE_PATH=str(Path(folder)/'soak.db'), PYTHONDONTWRITEBYTECODE='1')
        command = [sys.executable, '-B', str(Path(__file__).resolve())]
        subprocess.run(command+['--seed'], env=env, cwd=ROOT, check=True, capture_output=True, text=True)
        completed, reviews = set(), set()
        for tick in range(1, 11):
            workers = [subprocess.Popen(command+['--step', str(tick)], env=env, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
            ids = set()
            for worker in workers:
                output, error = worker.communicate(timeout=120)
                assert worker.returncode == 0, error
                result = json.loads(output)['cycle']
                ids.add(result['id'])
            assert len(ids) == 1
            # Terminal replay after all worker processes have exited.
            replay = subprocess.run(command+['--step', str(tick)], env=env, cwd=ROOT, check=True, capture_output=True, text=True)
            result = json.loads(replay.stdout)['cycle']
            assert result['id'] in ids
            assert result['learning_state'] == ('review' if tick % 5 == 0 else 'completed')
            (reviews if tick % 5 == 0 else completed).add(result['id'])
        assert len(completed) == 8 and len(reviews) == 2
    assert not Path(folder).exists()
    print('G8_ACCELERATED_10_CYCLES_4_PROCESSES=PASS')
    print('G8_RESTART_INJECTION=PASS')
    print('G8_FAILURE_REVIEW_NO_REGENERATION=PASS')
    print('G8_DUPLICATE_CYCLE_COUNT=0')
    print('G8_PUBLISH_INTENT_COUNT=0')
    print('G8_REAL_72H_SOAK=NOT_RUN')
    print('G8_TEMP_CLEANUP=PASS')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        step(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
    else:
        main()
