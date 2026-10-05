"""Network-free proof that only zero-write human YouTube claims may resume."""
import gc
import json
import socket
import sqlite3
import sys
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import human_youtube_publish_recovery_smoke as base
from publish import execution, manager, policy
from publish.adapters import youtube_api

fixture = base.fixture


@contextmanager
def test_db():
    conn = sqlite3.connect(fixture.DB)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


class BrokenResolver:
    def prepare(self, asset):
        raise RuntimeError('sensitive URL and token must never be stored')


class MissingPath:
    def prepare(self, asset):
        return base.SimpleNamespace(file_path=str(fixture.TEMP.name) + '/missing.mp4', cleanup=lambda: None)


def counts(task_id):
    return (len(base.rows(task_id, 'publish_write_intents')),
            len(base.rows(task_id, 'publish_operation_events')))


def assert_prewrite(task_id, stage):
    task = manager.get_publish_task(task_id)
    assert task['status'] == 'review' and task['execution_claim']
    assert task['error_message'] == 'HUMAN_PREWRITE_' + stage + '_FAILED'
    evidence = json.loads(task['policy_evidence'])
    assert evidence['human_prewrite_failure']['stage'] == stage
    assert evidence['human_prewrite_failure']['code'] == task['error_message']
    assert 'sensitive' not in json.dumps(evidence) + task['error_message']
    assert counts(task_id) == (0, 0)
    assert not task['provider_operation_id'] and not task['platform_video_id']
    return task


def denied(task_id, resolver=None):
    try:
        execution.resume_human_authorized_prewrite_publish_task(task_id, asset_resolver=resolver or base.Resolver())
    except ValueError:
        return
    raise AssertionError('unsafe human resume was accepted')


def main():
    assert fixture.DB.resolve() != (fixture.ROOT / 'os/database/os.db').resolve()
    fixture.quality.init_quality_table()
    manager._init_db()
    with patch.object(socket.socket, 'connect', fixture.blocked), patch.object(socket, 'getaddrinfo', fixture.blocked):
        # Each stage must leave a durable, sanitized and genuinely zero-write review.
        for stage in ('ASSET_DOWNLOAD', 'CREDENTIAL_BUILD', 'AUTHORIZED_SESSION_BUILD',
                      'VIDEO_PATH_VALIDATION', 'INITIALIZE_INTENT'):
            with ExitStack() as stack:
                task_id, transport = base.setup_case(stack)
                adapter = execution.get_adapter('youtube')
                resolver = base.Resolver()
                if stage == 'ASSET_DOWNLOAD':
                    resolver = BrokenResolver()
                elif stage == 'CREDENTIAL_BUILD':
                    stack.enter_context(patch.object(adapter, '_credentials_for_account',
                        side_effect=RuntimeError('sensitive credential detail')))
                elif stage == 'AUTHORIZED_SESSION_BUILD':
                    stack.enter_context(patch.object(youtube_api, 'build_authorized_session',
                        side_effect=RuntimeError('sensitive session detail')))
                elif stage == 'VIDEO_PATH_VALIDATION':
                    resolver = MissingPath()
                else:
                    with test_db() as conn:
                        conn.execute("""CREATE TRIGGER deny_prewrite_intent BEFORE INSERT ON publish_write_intents
                            BEGIN SELECT RAISE(ABORT, 'sensitive intent detail'); END""")
                try:
                    execution.execute_human_authorized_publish_task(task_id, asset_resolver=resolver)
                finally:
                    if stage == 'INITIALIZE_INTENT':
                        with test_db() as conn:
                            conn.execute('DROP TRIGGER deny_prewrite_intent')
                assert_prewrite(task_id, stage)
                assert transport.posts == transport.puts == 0
        print('FIVE_SANITIZED_PREWRITE_FAILURES=PASS')

        # A legacy review has no new diagnostic marker; the original claim remains the owner.
        with ExitStack() as stack:
            task_id, transport = base.setup_case(stack)
            execution.execute_human_authorized_publish_task(task_id, asset_resolver=BrokenResolver())
            original = assert_prewrite(task_id, 'ASSET_DOWNLOAD')
            with test_db() as conn:
                evidence = json.loads(original['policy_evidence'])
                evidence.pop('human_prewrite_failure')
                conn.execute("UPDATE publish_tasks SET policy_evidence=?,error_message=? WHERE id=?",
                    (json.dumps(evidence), 'HUMAN_EXTERNAL_OUTCOME_REQUIRES_REVIEW', task_id))
            result = execution.resume_human_authorized_prewrite_publish_task(task_id, asset_resolver=base.Resolver())
            assert result['task']['status'] == 'published'
            assert result['task']['execution_claim'] == original['execution_claim']
            assert transport.posts == transport.puts == 1 and transport.privacy == 'private'
            denied(task_id)
            assert transport.posts == 1
        print('LEGACY_ZERO_WRITE_SAME_OWNER_RESUME=PASS')
        print('SECOND_RESUME_REJECTED=PASS')

        # Durable intent or session evidence forbids a new upload session, even in review.
        for table, sql, values in (
            ('intent', 'INSERT INTO publish_write_intents(task_id,stage,claim,created_at) VALUES(?,?,?,?)',
             lambda t: (t, 'youtube_initialize', manager.get_publish_task(t)['execution_claim'], policy.now().isoformat())),
            ('event', 'INSERT INTO publish_operation_events(task_id,operation_id,operation_status,claim,created_at) VALUES(?,?,?,?,?)',
             lambda t: (t, 'a' * 64, 'SESSION_CREATED', manager.get_publish_task(t)['execution_claim'], policy.now().isoformat())),
        ):
            with ExitStack() as stack:
                task_id, transport = base.setup_case(stack)
                execution.execute_human_authorized_publish_task(task_id, asset_resolver=BrokenResolver())
                with test_db() as conn:
                    conn.execute(sql, values(task_id))
                denied(task_id)
                assert transport.posts == 0
        print('INTENT_OR_SESSION_RECOVERY_REJECTED=PASS')

        for field, value in (('title', 'changed'), ('privacy_status', 'public'),
                             ('asset_id', 'other-asset')):
            with ExitStack() as stack:
                task_id, transport = base.setup_case(stack)
                execution.execute_human_authorized_publish_task(task_id, asset_resolver=BrokenResolver())
                with test_db() as conn:
                    conn.execute(f'UPDATE publish_tasks SET {field}=? WHERE id=?', (value, task_id))
                denied(task_id)
                assert transport.posts == 0
        print('TASK_IDENTITY_DRIFT_REJECTED=PASS')

        for column, value in (('status', 'REVIEW'), ('source_fingerprint', 'drifted-source')):
            with ExitStack() as stack:
                task_id, transport = base.setup_case(stack)
                execution.execute_human_authorized_publish_task(task_id, asset_resolver=BrokenResolver())
                with test_db() as conn:
                    result_id = conn.execute('SELECT production_result_id FROM video_assets WHERE asset_id=?',
                        (manager.get_publish_task(task_id)['asset_id'],)).fetchone()[0]
                    conn.execute(f'UPDATE asset_quality_checks SET {column}=? WHERE production_result_id=?',
                        (value, result_id))
                denied(task_id)
                assert transport.posts == 0
        print('QUALITY_AND_SOURCE_DRIFT_REJECTED=PASS')

        with ExitStack() as stack:
            task_id, transport = base.setup_case(stack)
            execution.execute_human_authorized_publish_task(task_id, asset_resolver=BrokenResolver())
            account_id = manager.get_publish_task(task_id)['account_id']
            with test_db() as conn:
                conn.execute('UPDATE oauth_tokens SET expires_at=? WHERE account_id=?',
                    ((policy.now() - timedelta(minutes=1)).isoformat(), account_id))
            claimed = manager.get_publish_task(task_id)
            denied(task_id)
            after = manager.get_publish_task(task_id)
            assert after['status'] == 'review' and after['execution_claim'] == claimed['execution_claim']
            assert transport.posts == 0
            recovered = execution.resume_human_authorized_prewrite_publish_task(
                task_id, credential_refresh_authorized=True, asset_resolver=base.Resolver())
            assert recovered['task']['status'] == 'published' and transport.posts == 1
        print('EXPIRED_TOKEN_GATE_AND_AUTHORIZED_RESUME=PASS')
    gc.collect()
    fixture.TEMP.cleanup()


if __name__ == '__main__':
    main()
