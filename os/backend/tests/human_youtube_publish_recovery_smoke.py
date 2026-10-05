"""Offline proof of one human-authorized YouTube upload and local recovery."""
import gc
import json
import requests
import socket
import sqlite3
import sys
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g4d_asset_quality_smoke as fixture

from accounts.manager import create_account
from oauth.manager import create_token
from oauth.providers.youtube import YOUTUBE_UPLOAD_SCOPE
from publish import execution, manager, policy
from publish.adapters import youtube, youtube_api
from publish.models import PublishTask
from publish.orchestrator import PublishContractError, execute_publish_task
from publish.registry import register_adapter
from publish.queue import PublishQueue
from publish.worker import PublishWorker


class SimulatedCrash(BaseException):
    pass


class Reply:
    def __init__(self, payload=None, headers=None):
        self.status_code = 200
        self.payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class Transport:
    def __init__(self, task_id, *, crash_before_published=False):
        self.task_id = task_id
        self.crash_before_published = crash_before_published
        self.posts = self.puts = 0
        self.privacy = None
        self.second_execution_checked = False
        self.timeout_then_probe = False

    def post(self, url, **kwargs):
        assert kwargs['allow_redirects'] is False
        assert self.posts == 0
        self.privacy = kwargs['json']['status']['privacyStatus']
        assert self.privacy == 'private'
        with sqlite3.connect(fixture.DB) as conn:
            assert conn.execute("SELECT COUNT(*) FROM publish_write_intents WHERE task_id=? AND stage='youtube_initialize'",
                                (self.task_id,)).fetchone()[0] == 1
        conn.close()
        self.posts += 1
        second = execution.execute_human_authorized_publish_task(self.task_id)
        assert second['executed'] is False
        self.second_execution_checked = True
        return Reply(headers={'Location': 'https://www.googleapis.com/upload/youtube/v3/videos?session=opaque'})

    def put(self, url, **kwargs):
        assert kwargs['allow_redirects'] is False
        with sqlite3.connect(fixture.DB) as conn:
            assert conn.execute("SELECT COUNT(*) FROM publish_write_intents WHERE task_id=? AND stage LIKE 'youtube_chunk_%'",
                                (self.task_id,)).fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM publish_operation_events WHERE task_id=? AND operation_status='SESSION_CREATED'",
                                (self.task_id,)).fetchone()[0] == 1
        conn.close()
        self.puts += 1
        if self.timeout_then_probe and self.puts == 1:
            raise requests.Timeout('offline simulated chunk timeout')
        if self.timeout_then_probe and self.puts == 2:
            assert kwargs['data'] == b''
            with sqlite3.connect(fixture.DB) as conn:
                assert conn.execute("SELECT COUNT(*) FROM publish_write_intents WHERE task_id=? AND stage='youtube_resume_probe_0'",
                                    (self.task_id,)).fetchone()[0] == 1
            conn.close()
        if self.crash_before_published:
            raise SimulatedCrash()
        return Reply({'id': 'yt-private-proof-1'})


class Resolver:
    def __init__(self):
        self.file = Path(fixture.TEMP.name) / 'human-youtube-test.mp4'
        self.file.write_bytes(b'x' * 65536)

    def prepare(self, asset):
        return SimpleNamespace(file_path=str(self.file), cleanup=lambda: None)


def setup_case(stack):
    account = create_account(SimpleNamespace(platform='youtube', account_name='offline', status='connected'))
    create_token({'account_id': account['id'], 'provider': 'youtube',
                  'access_token': 'offline-sentinel', 'refresh_token': 'offline-refresh-sentinel',
                  'expires_at': (policy.now() + timedelta(hours=1)).isoformat(),
                  'scopes': [YOUTUBE_UPLOAD_SCOPE]})
    adapter = youtube.YouTubeAdapter()
    register_adapter('youtube', adapter, replace=True)
    stack.enter_context(patch.object(adapter, '_credentials_for_account', lambda aid, **kw: object()))
    result = fixture.source()
    quality = fixture.evaluate(result)
    assert quality['status'] == 'PASS'
    payload = PublishTask(asset_id=quality['asset_id'], video_id=result['video_id'],
                          platform='youtube', account_id=account['id'], title='Private education',
                          privacy_status='private')
    created = manager.create_or_get_publish_task(payload)
    assert created['created']
    task_id = created['task']['id']
    transport = Transport(task_id)
    stack.enter_context(patch.object(youtube_api, 'build_authorized_session', lambda _: transport))
    return task_id, transport


def rows(task_id, table):
    with sqlite3.connect(fixture.DB) as conn:
        found = conn.execute(f'SELECT * FROM {table} WHERE task_id=?', (task_id,)).fetchall()
    conn.close()
    return found


def main():
    assert fixture.DB.resolve() != (fixture.ROOT / 'os/database/os.db').resolve()
    fixture.quality.init_quality_table()
    manager._init_db()
    with patch.object(socket.socket, 'connect', fixture.blocked), patch.object(socket, 'getaddrinfo', fixture.blocked):
        with ExitStack() as stack:
            task_id, transport = setup_case(stack)
            try:
                execute_publish_task(task_id)
            except PublishContractError:
                pass
            else:
                raise AssertionError('legacy route did not fail closed')
            queue = PublishQueue(); queue.add_task(task_id)
            try:
                PublishWorker(queue).run_once()
            except RuntimeError:
                pass
            else:
                raise AssertionError('legacy worker did not fail closed')
            assert not rows(task_id, 'publish_write_intents')
            result = execution.execute_human_authorized_publish_task(task_id, asset_resolver=Resolver())
            task = result['task']
            assert task['status'] == 'published' and task['platform_video_id'] == 'yt-private-proof-1', (
                task['status'], task['error_message'], transport.posts, transport.puts,
                rows(task_id, 'publish_operation_events'))
            assert task['published_url'] == 'https://www.youtube.com/watch?v=yt-private-proof-1'
            assert task['execution_claim'] and task['provider_operation_status'] == 'PUBLISHED'
            assert transport.posts == 1 and transport.puts == 1 and transport.privacy == 'private'
            assert transport.second_execution_checked
            assert len(rows(task_id, 'publish_write_intents')) == 2
            assert [r[3] for r in rows(task_id, 'publish_operation_events')] == ['SESSION_CREATED', 'PUBLISHED']
            assert execution.execute_human_authorized_publish_task(task_id)['executed'] is False
            assert transport.posts == 1 and transport.puts == 1
            print('HUMAN_CLAIM_AND_DURABLE_INTENT=PASS')
            print('HUMAN_SESSION_AND_PUBLISHED_CORRELATION=PASS')
            print('PRIVATE_INITIALIZE_PAYLOAD=PASS')
            print('SECOND_EXECUTION_NO_WRITE=PASS')

        with ExitStack() as stack:
            task_id, transport = setup_case(stack)
            transport.timeout_then_probe = True
            result = execution.execute_human_authorized_publish_task(task_id, asset_resolver=Resolver())
            assert result['task']['status'] == 'published'
            assert transport.posts == 1 and transport.puts == 2
            assert len(rows(task_id, 'publish_write_intents')) == 3
            print('SAME_SESSION_RESUME_PROBE_INTENT=PASS')

        with ExitStack() as stack:
            task_id, transport = setup_case(stack)
            try:
                execution.execute_human_authorized_publish_task(
                    task_id, asset_resolver=Resolver(), before_finalization=lambda: (_ for _ in ()).throw(SimulatedCrash()))
            except SimulatedCrash:
                pass
            else:
                raise AssertionError('crash was not simulated')
            assert manager.get_publish_task(task_id)['status'] == 'publishing'
            assert len([r for r in rows(task_id, 'publish_operation_events') if r[3] == 'PUBLISHED']) == 1
            recovered = execution.reconcile_human_authorized_publish_task(task_id)
            assert recovered['status'] == 'published' and recovered['platform_video_id'] == 'yt-private-proof-1'
            assert transport.posts == 1 and transport.puts == 1
            print('CRASH_AFTER_SUCCESS_READ_ONLY_RECOVERY=PASS')

        with ExitStack() as stack:
            task_id, transport = setup_case(stack)
            try:
                execution.execute_human_authorized_publish_task(
                    task_id, asset_resolver=Resolver(), before_finalization=lambda: (_ for _ in ()).throw(SimulatedCrash()))
            except SimulatedCrash:
                pass
            with sqlite3.connect(fixture.DB) as conn:
                conn.execute("UPDATE publish_tasks SET title='changed after claim' WHERE id=?", (task_id,))
            conn.close()
            recovered = execution.reconcile_human_authorized_publish_task(task_id)
            assert recovered['status'] == 'review' and not recovered['platform_video_id']
            assert transport.posts == 1 and transport.puts == 1
            print('HUMAN_TASK_DRIFT_REJECTED=PASS')

        with ExitStack() as stack:
            task_id, transport = setup_case(stack)
            transport.crash_before_published = True
            try:
                execution.execute_human_authorized_publish_task(task_id, asset_resolver=Resolver())
            except SimulatedCrash:
                pass
            else:
                raise AssertionError('crash was not simulated')
            assert len(rows(task_id, 'publish_operation_events')) == 1
            recovered = execution.reconcile_human_authorized_publish_task(task_id)
            assert recovered['status'] == 'review' and not recovered['platform_video_id']
            assert execution.execute_human_authorized_publish_task(task_id)['executed'] is False
            assert transport.posts == 1 and transport.puts == 1
            print('CRASH_BEFORE_PUBLISHED_NO_RETRY=PASS')

        with ExitStack() as stack:
            task_id, transport = setup_case(stack)
            with sqlite3.connect(fixture.DB) as conn:
                conn.execute('UPDATE oauth_tokens SET expires_at=? WHERE account_id=?',
                             ((policy.now() - timedelta(minutes=1)).isoformat(), manager.get_publish_task(task_id)['account_id']))
            conn.close()
            try:
                execution.execute_human_authorized_publish_task(task_id, asset_resolver=Resolver())
            except ValueError as exc:
                assert str(exc) == 'YOUTUBE_TOKEN_REFRESH_REQUIRES_EXPLICIT_AUTHORIZATION'
            else:
                raise AssertionError('expired token was accepted without authorization')
            assert manager.get_publish_task(task_id)['status'] == 'pending'
            assert transport.posts == transport.puts == 0
            print('OAUTH_REFRESH_AUTHORIZATION_GATE=PASS')
        with ExitStack() as stack:
            task_id, transport = setup_case(stack)
            from oauth.providers import youtube as youtube_oauth
            stack.enter_context(patch.object(youtube_oauth.YouTubeOAuthProvider, 'ensure_valid_token',
                                             side_effect=AssertionError('refresh forbidden')))
            stack.enter_context(patch.object(youtube_oauth.YouTubeOAuthProvider, 'build_google_credentials',
                                             side_effect=lambda token: token))
            fresh_adapter = youtube.YouTubeAdapter()
            credentials = fresh_adapter._credentials_for_account(
                manager.get_publish_task(task_id)['account_id'], credential_refresh_authorized=False)
            assert credentials['access_token'] == 'offline-sentinel'
            assert credentials['refresh_token'] is None
            print('NO_IMPLICIT_OAUTH_REFRESH=PASS')
    gc.collect()
    fixture.TEMP.cleanup()


if __name__ == '__main__':
    main()
