"""Offline operational projection/recovery; no new execution engine."""
from test_database_helper import TEST_DATABASE_PATH
import hashlib
import importlib
import json
import os
import socket
import sqlite3
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from production.runtime import health
from production.tasks.manager import init_tasks_table, create_task
from production.runtime.manager import init_runtime_table, create_job
from production.results.manager import init_results_table
from assets.quality import init_quality_table
from publish.manager import _init_db as init_publish
from intelligence.learning import init_learning
from intelligence.autonomy import get_autonomy_settings, update_autonomy_settings


def main():
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        assert health.runtime_health()['status'] == 'not_initialized'
        for _ in range(2):
            init_tasks_table(); init_runtime_table(); init_results_table()
            init_quality_table(); init_publish(); init_learning(); get_autonomy_settings()
        task = create_task({'provider': 'github', 'task_type': 'video_batch', 'parameters': {'content_id': 'offline'}})
        job = create_job({'task_id': task.id, 'provider': 'github', 'job_type': 'github_runtime', 'status': 'running'})
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            conn.execute("UPDATE runtime_jobs SET updated_at='2000-01-01T00:00:00',error='test-secret-sentinel' WHERE id=?", (job['id'],))
        conn.close()
        before = hashlib.sha256(TEST_DATABASE_PATH.read_bytes()).hexdigest()
        observed = health.runtime_health()
        assert observed['kill_switch_active'] and not observed['autonomous_execution_allowed']
        assert any(r['entity'] == 'runtime_jobs' and r['id'] == job['id'] for r in observed['review_queue'])
        assert 'test-secret-sentinel' not in json.dumps(observed)
        assert observed['provider_live_readiness'] == 'NOT_CHECKED'
        with ThreadPoolExecutor(max_workers=4) as pool:
            views = list(pool.map(lambda _: health.runtime_health(), range(20)))
        assert all(v == observed for v in views)
        assert hashlib.sha256(TEST_DATABASE_PATH.read_bytes()).hexdigest() == before
        recovered = health.reconcile_local_evidence()
        assert recovered['recovered'] == [] and recovered['external_requests'] == 0
        assert recovered['review']
        importlib.reload(health)
        assert health.runtime_health() == observed
        update_autonomy_settings(autonomy_enabled=True, kill_switch_active=True)
        assert not health.runtime_health()['autonomous_execution_allowed']
        # SQLite backup is consistent and restore proof never overwrites a DB.
        backup = TEST_DATABASE_PATH.with_name('backup-proof.db')
        src, dest = sqlite3.connect(TEST_DATABASE_PATH), sqlite3.connect(backup)
        try:
            src.backup(dest)
            assert dest.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert dest.execute('SELECT COUNT(*) FROM runtime_jobs').fetchone()[0] == 1
        finally:
            src.close(); dest.close()
        # Duplicate history is surfaced, not removed or silently selected.
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            conn.execute('DROP INDEX uq_runtime_jobs_task_id')
            conn.execute("INSERT INTO runtime_jobs(task_id,provider,status) VALUES(?,'github','running')", (task.id,))
        conn.close()
        assert health.runtime_health()['duplicate_groups']['runtime_jobs'] == 1
        assert not health.runtime_health()['ready']
        from production.runtime import poller
        worker = Mock()
        worker.poll.side_effect = RuntimeError('test-secret-sentinel')
        with patch.object(poller, 'get_jobs', return_value=[{'id': 1, 'provider': 'github', 'status': 'running'}]), patch.object(poller, 'get_provider', return_value=Mock()):
            result = poller.ProductionRuntimePoller(worker=worker).poll_once()
        assert result['failed'] == 1 and 'test-secret-sentinel' not in json.dumps(result)
    print('G7_SCHEMA_BOOTSTRAP_IDEMPOTENT=PASS')
    print('G7_STALE_REVIEW_NO_REDISPATCH=PASS')
    print('G7_READONLY_HEALTH_CONCURRENCY=PASS')
    print('G7_RESTART_READBACK=PASS')
    print('G7_SECRET_PROJECTION=PASS')
    print('G7_KILL_SWITCH_PRECEDENCE=PASS')
    print('G7_BACKUP_INTEGRITY=PASS')
    print('G7_DUPLICATE_HISTORY_PRESERVED=PASS')


if __name__ == '__main__':
    main()
