"""Network-free proof that only zero-write human YouTube claims may resume."""
import gc
import json
import os
import tempfile
import socket
import sqlite3
import sys
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import human_youtube_publish_recovery_smoke as base
from assets.remote_media import MediaFailure
from assets import remote_media
from config import network
from publish import execution, manager, policy
from publish import asset_resolver as publish_assets
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
        raise RuntimeError('secret-bearing arbitrary message')


class FailureResolver:
    def __init__(self, error):
        self.error = error

    def prepare(self, asset):
        raise self.error


class MissingPath:
    def prepare(self, asset):
        return base.SimpleNamespace(file_path=str(fixture.TEMP.name) + '/missing.mp4', cleanup=lambda: None)


class FakeMediaResponse:
    status_code = 200
    headers = {'Content-Type': 'video/mp4', 'Content-Length': '65536'}

    def __init__(self, fail_midstream=False):
        self.fail_midstream = fail_midstream

    def iter_content(self, chunk_size):
        yield b'x' * 32768
        if self.fail_midstream:
            raise requests.ConnectionError('secret-bearing transport detail')
        yield b'x' * 32768

    def close(self):
        pass


class FakePublishSession:
    def __init__(self, *, fail_midstream=False):
        self.fail_midstream = fail_midstream
        self.gets = 0

    def get(self, url, **kwargs):
        assert url.startswith('https://') and kwargs['allow_redirects'] is False
        self.gets += 1
        return FakeMediaResponse(self.fail_midstream)


class FakeDirectSession:
    def get(self, url, **kwargs):
        return FakeMediaResponse()


def staging_proofs():
    # The quality downloader rejects a simulated 121-second total duration;
    # the publish resolver has no total wall-clock deadline.
    with patch.object(remote_media.time, 'monotonic', side_effect=[0, 121]):
        try:
            with remote_media.RemoteMedia(session=FakeDirectSession(),
                    resolver=lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '',
                                                         ('8.8.8.8', 443))]).download(
                    'https://media.example.invalid/clip.mp4', storage_type='github_pages'):
                pass
        except MediaFailure as error:
            assert error.reason == 'DOWNLOAD_TIMEOUT'
        else:
            raise AssertionError('G4-D total deadline was not enforced')

    network._init_db()  # Isolated fixture DB only.
    fake_proxy = 'http://proxy.invalid:7897'
    with test_db() as conn:
        conn.execute("INSERT OR REPLACE INTO network_proxy_settings(id,mode,proxy_url,updated_at) VALUES(1,'manual',?,?)",
                     (fake_proxy, policy.now().isoformat()))
    sessions = []

    def make_session():
        assert os.environ.get('HTTPS_PROXY') == fake_proxy
        session = FakePublishSession()
        sessions.append(session)
        return session

    with patch.dict(os.environ), patch.object(publish_assets.requests, 'Session', side_effect=make_session):
        asset = {'asset_id': 'synthetic', 'storage_type': 'github_pages',
                 'asset_url': 'https://media.example.invalid/clip.mp4'}
        prepared = publish_assets.AssetResolver().prepare(asset)
        assert os.path.getsize(prepared.file_path) == 65536
        path = prepared.file_path
        prepared.cleanup()
        assert not os.path.exists(path) and sessions[-1].gets == 1
        try:
            publish_assets.AssetResolver().prepare({**asset, 'asset_url': 'http://media.example.invalid/clip.mp4'})
        except publish_assets.AssetResolutionError:
            pass
        else:
            raise AssertionError('github_pages HTTP URL was accepted')
        assert sessions[-1].gets == 0
        print('PUBLISH_ASSET_NO_TOTAL_120S_DEADLINE=PASS')
        print('PROXY_CONFIG_APPLIED=PASS')
        print('GITHUB_PAGES_HTTPS_REQUIRED=PASS')

        # A legacy Task16-like review is resumed by the default publish resolver.
        with ExitStack() as stack:
            task_id, transport = base.setup_case(stack)
            execution.execute_human_authorized_publish_task(task_id, asset_resolver=BrokenResolver())
            old = manager.get_publish_task(task_id)
            paths = []
            original_prepare = publish_assets.AssetResolver.prepare

            def capture_prepare(self, video_asset):
                staged = original_prepare(self, video_asset)
                paths.append(staged.file_path)
                return staged

            with patch.object(publish_assets.AssetResolver, 'prepare', capture_prepare):
                result = execution.resume_human_authorized_prewrite_publish_task(task_id)
            assert result['task']['status'] == 'published'
            assert result['task']['execution_claim'] == old['execution_claim']
            assert len(paths) == 1 and not os.path.exists(paths[0])
            assert transport.posts == 1 and transport.puts == 1
            assert len(base.rows(task_id, 'publish_write_intents')) == 2
            assert len([r for r in base.rows(task_id, 'publish_operation_events') if r[3] == 'PUBLISHED']) == 1
            denied(task_id)
            assert transport.posts == 1
        print('DEFAULT_RESOLVER_ZERO_WRITE_RESUME=PASS')
        print('SECOND_RECOVERY_NO_SESSION=PASS')

        for failure in ('returned', 'raised'):
            with ExitStack() as stack:
                task_id, transport = base.setup_case(stack)
                adapter = execution.get_adapter('youtube')
                paths = []

                def fail_publish(asset, account_id, **kwargs):
                    paths.append(kwargs['video_path'])
                    if failure == 'raised':
                        raise RuntimeError('secret-bearing adapter detail')
                    return {'status': 'failed', 'failure_stage': 'CREDENTIAL_BUILD'}

                stack.enter_context(patch.object(adapter, 'publish_video', side_effect=fail_publish))
                result = execution.execute_human_authorized_publish_task(task_id)
                assert result['task']['status'] == 'review'
                assert len(paths) == 1 and not os.path.exists(paths[0])
                assert transport.posts == 0 and counts(task_id) == (0, 0)
        print('PUBLISH_TEMP_CLEANUP=PASS')

    # A partial stream failure must remove its TEMP file and persist no raw detail.
    real_named_temp = tempfile.NamedTemporaryFile
    def external_named_temp(**kwargs):
        return real_named_temp(dir=fixture.TEMP.name, **kwargs)
    session = FakePublishSession(fail_midstream=True)
    before = set(Path(fixture.TEMP.name).glob('remote-pay-guide-publish-*'))
    with patch.object(publish_assets.tempfile, 'NamedTemporaryFile', side_effect=external_named_temp):
        with ExitStack() as stack:
            task_id, transport = base.setup_case(stack)
            resolver = publish_assets.AssetResolver(session=session)
            result = execution.execute_human_authorized_publish_task(task_id, asset_resolver=resolver)
            assert result['task']['status'] == 'review'
            assert result['task']['error_message'] == 'HUMAN_PREWRITE_ASSET_DOWNLOAD_FAILED'
            evidence = json.loads(result['task']['policy_evidence'])['human_prewrite_failure']
            assert evidence['reason'] == 'ASSET_DOWNLOAD_FAILURE_UNCLASSIFIED'
            assert 'secret-bearing' not in result['task']['policy_evidence']
            assert transport.posts == 0 and counts(task_id) == (0, 0)
    after = set(Path(fixture.TEMP.name).glob('remote-pay-guide-publish-*'))
    assert after == before
    print('PARTIAL_DOWNLOAD_CLEANUP_AND_SAFE_FAILURE=PASS')


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
    if stage == 'ASSET_DOWNLOAD':
        assert evidence['human_prewrite_failure']['reason'] == 'ASSET_DOWNLOAD_FAILURE_UNCLASSIFIED'
    else:
        assert 'reason' not in evidence['human_prewrite_failure']
    assert 'secret-bearing arbitrary message' not in json.dumps(evidence) + task['error_message']
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

        for reason, expected in (
            ('REMOTE_FETCH_UNAVAILABLE', 'REMOTE_FETCH_UNAVAILABLE'),
            ('DNS_UNAVAILABLE', 'DNS_UNAVAILABLE'),
            ('SOME_FUTURE_UNTRUSTED_TEXT', 'ASSET_DOWNLOAD_FAILURE_UNCLASSIFIED'),
        ):
            with ExitStack() as stack:
                task_id, transport = base.setup_case(stack)
                execution.execute_human_authorized_publish_task(
                    task_id, asset_resolver=FailureResolver(MediaFailure('REVIEW', reason)))
                task = manager.get_publish_task(task_id)
                evidence = json.loads(task['policy_evidence'])['human_prewrite_failure']
                assert task['status'] == 'review'
                assert task['error_message'] == 'HUMAN_PREWRITE_ASSET_DOWNLOAD_FAILED'
                assert evidence['stage'] == 'ASSET_DOWNLOAD' and evidence['reason'] == expected
                if reason != expected:
                    assert reason not in task['policy_evidence']
                assert counts(task_id) == (0, 0) and transport.posts == 0
        print('SAFE_MEDIA_FAILURE_ALLOWLIST=PASS')

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

        with ExitStack() as stack:
            task_id, transport = base.setup_case(stack)
            execution.execute_human_authorized_publish_task(task_id, asset_resolver=BrokenResolver())
            with test_db() as conn:
                conn.execute("UPDATE publish_tasks SET provider_operation_id='correlated' WHERE id=?", (task_id,))
            denied(task_id)
            assert transport.posts == 0
        print('PROVIDER_CORRELATION_RECOVERY_REJECTED=PASS')

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
        staging_proofs()
    gc.collect()
    fixture.TEMP.cleanup()


if __name__ == '__main__':
    main()
