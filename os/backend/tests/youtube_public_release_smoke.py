"""Isolated, network-free proof of one human-authorized YouTube privacy release."""
import json
import gc
import socket
import sqlite3
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import human_youtube_publish_recovery_smoke as fixture

from oauth.manager import create_token
from oauth.providers.youtube import (YOUTUBE_SCOPE_PROFILES, YOUTUBE_UPLOAD_SCOPE,
    YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE, YOUTUBE_FORCE_SSL_SCOPE)
from publish import execution, manager, policy
from publish.adapters import youtube_api


class Reply:
    status_code = 200
    def __init__(self, body):
        self.body = body
    def json(self):
        return self.body
    def raise_for_status(self):
        return None


class FakeReleaseTransport:
    def __init__(self, task_id, *, outcome='success'):
        self.task_id = task_id
        self.outcome = outcome
        self.gets = self.puts = 0
        self.remote_privacy = 'private'
        self.body = None

    def get(self, url, **kwargs):
        assert url == 'https://www.googleapis.com/youtube/v3/videos'
        assert kwargs['params']['part'] == 'status,processingDetails'
        assert kwargs['allow_redirects'] is False
        self.gets += 1
        return Reply({'items': [{'id': kwargs['params']['id'], 'status': {
            'privacyStatus': self.remote_privacy, 'license': 'youtube', 'embeddable': False,
            'publicStatsViewable': False, 'selfDeclaredMadeForKids': False,
            'containsSyntheticMedia': True, 'publishAt': '2029-01-01T00:00:00Z',
            'uploadStatus': 'processed', 'madeForKids': False},
            'processingDetails': {'processingStatus': 'succeeded'}}]})

    def put(self, url, **kwargs):
        assert url == 'https://www.googleapis.com/youtube/v3/videos'
        assert kwargs['params'] == {'part': 'status'}
        assert kwargs['allow_redirects'] is False
        with sqlite3.connect(fixture.fixture.DB) as conn:
            assert conn.execute("SELECT COUNT(*) FROM publish_write_intents WHERE task_id=? AND stage='youtube_privacy_public'",
                                (self.task_id,)).fetchone()[0] == 1
        self.puts += 1
        self.body = kwargs['json']
        status = self.body['status']
        assert status == {'license': 'youtube', 'embeddable': False,
            'publicStatsViewable': False, 'selfDeclaredMadeForKids': False,
            'containsSyntheticMedia': True, 'privacyStatus': 'public'}
        if self.outcome == 'timeout':
            raise requests.Timeout('sentinel secret not persisted')
        if self.outcome == 'restricted':
            response = requests.Response()
            response.status_code = 403
            response._content = b'{"error":{"message":"Unverified API project cannot release public videos"}}'
            raise requests.HTTPError('sentinel secret not persisted', response=response)
        self.remote_privacy = 'public'
        return Reply({'id': self.body['id'], 'status': {'privacyStatus': 'public'}})


def rows(task_id, table, predicate='1=1'):
    with sqlite3.connect(fixture.fixture.DB) as conn:
        return conn.execute(f'SELECT * FROM {table} WHERE task_id=? AND {predicate}', (task_id,)).fetchall()


def make_published(stack):
    task_id, upload = fixture.setup_case(stack)
    assert not fixture.youtube.YouTubeAdapter().get_public_release_scope_readiness(
        manager.get_publish_task(task_id)['account_id'])['public_release_scope_ready']
    before = execution.execute_human_authorized_publish_task(task_id, asset_resolver=fixture.Resolver())['task']
    assert before['status'] == 'published' and before['privacy_status'] == 'private'
    create_token({'account_id': before['account_id'], 'provider': 'youtube',
        'access_token': 'offline-sentinel', 'refresh_token': 'offline-refresh-sentinel',
        'expires_at': (policy.now() + fixture.timedelta(hours=1)).isoformat(),
        'scopes': YOUTUBE_SCOPE_PROFILES['full_manage']})
    assert fixture.youtube.YouTubeAdapter().get_public_release_scope_readiness(
        before['account_id'])['public_release_scope_ready']
    return task_id, before


def main():
    assert fixture.fixture.DB.resolve() != (fixture.fixture.ROOT / 'os/database/os.db').resolve()
    assert YOUTUBE_SCOPE_PROFILES['publish'] == [YOUTUBE_UPLOAD_SCOPE]
    assert YOUTUBE_SCOPE_PROFILES['analytics'] == [YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE]
    assert YOUTUBE_SCOPE_PROFILES['full'] == [YOUTUBE_UPLOAD_SCOPE, YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE]
    assert YOUTUBE_SCOPE_PROFILES['full_manage'] == [YOUTUBE_UPLOAD_SCOPE, YOUTUBE_READ_SCOPE,
                                                     YOUTUBE_ANALYTICS_SCOPE, YOUTUBE_FORCE_SSL_SCOPE]
    print('SCOPE_PROFILE=PASS')
    manager._init_db()
    fixture.fixture.quality.init_quality_table()
    with patch.object(socket.socket, 'connect', fixture.fixture.blocked), patch.object(socket, 'getaddrinfo', fixture.fixture.blocked):
        with ExitStack() as stack:
            task_id, before = make_published(stack)
            print('SCOPE_READINESS=PASS')
            upload_evidence = [(r[2], r[3], r[4]) for r in rows(task_id, 'publish_operation_events')]
            transport = FakeReleaseTransport(task_id)
            stack.enter_context(patch.object(youtube_api, 'build_authorized_session', lambda _: transport))
            result = execution.execute_human_authorized_youtube_public_release(task_id)
            after = result['task']
            assert result['executed'] and transport.gets == 1 and transport.puts == 1
            assert after['status'] == 'published' and after['privacy_status'] == 'public'
            assert after['platform_video_id'] == before['platform_video_id']
            assert after['published_url'] == before['published_url']
            assert after['execution_claim'] == before['execution_claim']
            assert [(r[2], r[3], r[4]) for r in rows(task_id, 'publish_operation_events')[:2]] == upload_evidence
            assert len(rows(task_id, 'publish_write_intents', "stage='youtube_privacy_public'")) == 1
            assert len(rows(task_id, 'publish_operation_events', "operation_status='PRIVACY_PUBLIC'")) == 1
            assert json.loads(after['policy_evidence'])['youtube_public_release']['state'] == 'completed'
            print('PUBLIC_RELEASE_SUCCESS=PASS')
            print('STATUS_PRESERVATION=PASS')
            second = execution.execute_human_authorized_youtube_public_release(task_id)
            assert second['executed'] is False and transport.puts == 1
            print('SECOND_EXECUTION_NO_WRITE=PASS')

        with ExitStack() as stack:
            task_id, before = make_published(stack)
            transport = FakeReleaseTransport(task_id, outcome='timeout')
            stack.enter_context(patch.object(youtube_api, 'build_authorized_session', lambda _: transport))
            result = execution.execute_human_authorized_youtube_public_release(task_id)
            assert result['executed'] and transport.puts == 1
            assert result['task']['privacy_status'] == 'private' and result['task']['status'] == 'published'
            assert json.loads(result['task']['policy_evidence'])['youtube_public_release']['state'] == 'review'
            assert len(rows(task_id, 'publish_write_intents', "stage='youtube_privacy_public'")) == 1
            assert execution.execute_human_authorized_youtube_public_release(task_id)['executed'] is False
            assert transport.puts == 1
            print('AMBIGUOUS_PUT=PASS')
            transport.remote_privacy = 'public'
            transport.gets = 0
            recovered = execution.reconcile_human_authorized_youtube_public_release(task_id)
            assert recovered['privacy_status'] == 'public' and transport.gets == 1 and transport.puts == 1
            assert len(rows(task_id, 'publish_operation_events', "operation_status='PRIVACY_PUBLIC'")) == 1
            assert execution.reconcile_human_authorized_youtube_public_release(task_id)['privacy_status'] == 'public'
            print('READ_ONLY_RECONCILIATION=PASS')

        with ExitStack() as stack:
            task_id, before = make_published(stack)
            transport = FakeReleaseTransport(task_id, outcome='timeout')
            stack.enter_context(patch.object(youtube_api, 'build_authorized_session', lambda _: transport))
            execution.execute_human_authorized_youtube_public_release(task_id)
            result = execution.reconcile_human_authorized_youtube_public_release(task_id)
            assert result['privacy_status'] == 'private' and transport.puts == 1
            assert json.loads(result['policy_evidence'])['youtube_public_release']['state'] == 'review'
            print('PROVIDER_STILL_PRIVATE=PASS')

        with ExitStack() as stack:
            task_id, before = make_published(stack)
            transport = FakeReleaseTransport(task_id, outcome='restricted')
            stack.enter_context(patch.object(youtube_api, 'build_authorized_session', lambda _: transport))
            result = execution.execute_human_authorized_youtube_public_release(task_id)
            release = json.loads(result['task']['policy_evidence'])['youtube_public_release']
            assert result['task']['privacy_status'] == 'private' and transport.puts == 1
            assert release['reason'] == 'YOUTUBE_PUBLIC_RELEASE_PROJECT_RESTRICTED'
            assert 'sentinel' not in result['task']['policy_evidence']
            print('PROJECT_RESTRICTION=PASS')

    gc.collect()


if __name__ == '__main__':
    main()
