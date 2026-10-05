"""Network-free G5: real canonical quality/task/adapter code and fake transports."""
import gc
import io
import json
import socket
import sqlite3
import sys
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g4d_asset_quality_smoke as fixture
from accounts.manager import create_account
from intelligence.autonomy import update_autonomy_settings
from publish import manager, policy, execution
from publish.registry import register_adapter
from publish.adapters import instagram, facebook, youtube, youtube_api
from publish.queue import PublishQueue
from publish.worker import PublishWorker
from publish.scheduler import PublishScheduler
from publish.orchestrator import execute_publish_task

SECRET = 'G5_SECRET_SENTINEL'


class SimulatedCrash(BaseException):
    pass


def sql(statement, args=()):
    with sqlite3.connect(fixture.DB) as conn:
        values = conn.execute(statement, args).fetchall()
    conn.close()
    return values


def blocked(*args, **kwargs):
    raise AssertionError('REAL_NETWORK_FORBIDDEN')


class Reply:
    def __init__(self, payload=None, headers=None):
        self.status_code = 200
        self.headers = headers or {}
        self.payload = payload or {}
    def json(self):
        return self.payload
    def raise_for_status(self):
        pass


class Transport:
    def __init__(self, platform, *, fail_at=None, hook=None):
        self.platform, self.fail_at, self.hook = platform, fail_at, hook
        self.writes = []
        self.reads = []
        self.terminal_failure = False
        self.account_id = None
        self.upload_destination = None
        self.acknowledged = True
    def post(self, url, **kwargs):
        assert kwargs['allow_redirects'] is False
        # Durable intent must already be COMMITTED and readable by another conn.
        stage = ('youtube_initialize' if self.platform == 'youtube' else
                 'instagram_publish' if url.endswith('/media_publish') else
                 'instagram_container' if url.endswith('/media') else
                 'facebook_start' if kwargs.get('params', {}).get('upload_phase') == 'start' else
                 'facebook_finish' if kwargs.get('params', {}).get('upload_phase') == 'finish' else 'facebook_upload')
        # A second writer can acquire a transaction at the transport boundary:
        # the canonical executor must have committed/released its write lock.
        with sqlite3.connect(fixture.DB, timeout=5) as connection:
            connection.execute('BEGIN IMMEDIATE')
            intents = connection.execute('''SELECT i.stage FROM publish_write_intents i
                JOIN publish_tasks t ON t.id=i.task_id WHERE t.account_id=? AND t.platform=?
                AND t.execution_claim=i.claim AND i.stage=?''', (self.account_id, self.platform, stage)).fetchall()
            assert len(intents) == 1
        connection.close()
        self.writes.append(url)
        if self.hook:
            self.hook(len(self.writes))
        if self.fail_at == len(self.writes):
            raise TimeoutError(SECRET)
        if self.platform == 'youtube':
            return Reply(headers={'Location': self.upload_destination or 'https://www.googleapis.com/upload/youtube/v3/videos?token=' + SECRET})
        if url.endswith('/media'):
            return Reply({'id': 'container-1'})
        if url.endswith('/media_publish'):
            return Reply({'id': 'ig-media-1'})
        if kwargs.get('params', {}).get('upload_phase') == 'start':
            return Reply({'video_id': 'fb-video-1', 'upload_url': self.upload_destination or 'https://rupload.facebook.com/reel'})
        return Reply({'success': self.acknowledged})
    def put(self, url, **kwargs):
        assert kwargs['allow_redirects'] is False
        assert sql("SELECT stage FROM publish_write_intents WHERE stage LIKE 'youtube_chunk_%'")
        self.writes.append(url)
        return Reply({'id': 'yt-video-1'})
    def get(self, url, **kwargs):
        self.reads.append(url)
        return Reply({'status_code': 'ERROR' if self.terminal_failure else 'FINISHED', 'status': 'CREATED'})


class Resolver:
    def __init__(self):
        self.cleaned = 0
        self.file = Path(fixture.TEMP.name) / 'fake-media.mp4'
        self.file.write_bytes(b'x' * 65536)
    def prepare(self, asset):
        def cleanup():
            self.cleaned += 1
        return SimpleNamespace(file_path=str(self.file), cleanup=cleanup)


def environment(stack, platform='instagram', *, fail_at=None, hook=None):
    account = create_account(SimpleNamespace(platform=platform, account_name='offline', status='connected'))
    token = {'access_token': SECRET, 'provider': platform,
             'expires_at': (policy.now() + timedelta(hours=1)).isoformat(),
             'scopes': list(instagram.INSTAGRAM_PUBLISH_SCOPES if platform == 'instagram' else
                            facebook.FACEBOOK_PUBLISH_SCOPES if platform == 'facebook' else [youtube.YOUTUBE_UPLOAD_SCOPE])}
    transport = Transport(platform, fail_at=fail_at, hook=hook)
    transport.account_id = account['id']
    module = {'instagram': instagram, 'facebook': facebook, 'youtube': youtube}[platform]
    stack.enter_context(patch.object(policy, 'get_token', lambda _: token))
    stack.enter_context(patch.object(module, 'get_token', lambda _: token))
    if platform == 'youtube':
        adapter = youtube.YouTubeAdapter()
        stack.enter_context(patch.object(adapter, '_credentials_for_account', lambda _: object()))
        stack.enter_context(patch.object(youtube_api, 'build_authorized_session', lambda _: transport))
    else:
        stack.enter_context(patch.object(module, 'get_binding', lambda _: {'platform': platform, 'page_id': 'page1', 'instagram_user_id': 'ig1'}))
        stack.enter_context(patch.object(module, 'resolve_page_access_token', lambda *a: SECRET))
        adapter = (instagram.InstagramAdapter if platform == 'instagram' else facebook.FacebookAdapter)(transport=transport, live_publish_enabled=True)
    register_adapter(platform, adapter, replace=True)
    result = fixture.source()
    checked = fixture.evaluate(result)
    assert checked['status'] == 'PASS'
    payload = {'asset_id': checked['asset_id'], 'platform': platform, 'account_id': account['id'],
               'title': 'Safe payment verification', 'description': 'Education only', 'privacy_status': 'private'}
    return payload, transport, token, adapter, result


def task(payload):
    result = policy.prepare_autonomous_publish_task(payload)
    assert result['created'], result['policy']
    return result['task']['id']


def post_intent_checks():
    """Inject changes after a real committed intent, not before authorization."""
    cases = ('normal', 'kill', 'disabled', 'payload', 'source', 'owner',
             'terminal', 'account', 'scope', 'duplicate')
    for platform, stages in [('youtube', 2), ('instagram', 2), ('facebook', 3)]:
        for target in range(1, stages + 1):
            for case in cases:
                with ExitStack() as stack:
                    payload, transport, token, adapter, result = environment(stack, platform)
                    tid = task(payload)
                    connect = manager._connect
                    seen = []
                    owners = []
                    fresh = []
                    signals = policy.runtime_signals

                    class Connection:
                        def __init__(self):
                            self.inner = connect()
                            self.intent = False
                        def __getattr__(self, name):
                            return getattr(self.inner, name)
                        def execute(self, statement, args=()):
                            row = self.inner.execute(statement, args)
                            if statement.startswith('INSERT INTO publish_write_intents'):
                                self.intent = True
                            return row
                        def commit(self):
                            self.inner.commit()
                            if not self.intent:
                                return
                            self.intent = False
                            assert not self.inner.in_transaction
                            rows = sql('SELECT stage,claim FROM publish_write_intents WHERE task_id=?', (tid,))
                            assert len(rows) == len(seen) + 1
                            seen.append(len(rows))
                            owners.append(manager.get_publish_task(tid)['execution_claim'])
                            assert all(r[1] == owners[0] for r in rows)
                            if len(seen) != target:
                                return
                            if case == 'kill': update_autonomy_settings(kill_switch_active=True)
                            if case == 'disabled': update_autonomy_settings(autonomy_enabled=False)
                            if case == 'payload': sql("UPDATE publish_tasks SET title='drift' WHERE id=?", (tid,))
                            if case == 'source': sql("UPDATE production_results SET output='{}' WHERE id=?", (result['id'],))
                            if case == 'owner': sql("UPDATE publish_tasks SET execution_claim='changed-owner',status='review' WHERE id=?", (tid,))
                            if case == 'terminal': sql("UPDATE publish_tasks SET status='review' WHERE id=?", (tid,))
                            if case == 'account': sql("UPDATE accounts SET status='disconnected' WHERE id=?", (payload['account_id'],))
                            if case == 'scope': token['scopes'] = []
                            if case == 'duplicate':
                                sql("INSERT INTO publish_tasks(asset_id,platform,account_id,status) VALUES(?,?,?,'failed')",
                                    (payload['asset_id'], platform, payload['account_id']))

                    def fresh_signals(*args):
                        if seen:
                            fresh.append(len(seen))
                        return signals(*args)

                    stack.enter_context(patch.object(manager, '_connect', Connection))
                    stack.enter_context(patch.object(policy, 'runtime_signals', fresh_signals))
                    execution.execute_autonomous_publish_task(tid, asset_resolver=Resolver())
                    stored = manager.get_publish_task(tid)
                    expected = stages if case == 'normal' else target - 1
                    assert len(transport.writes) == expected, (platform, target, case)
                    assert target in fresh, (platform, target, case, 'no post-commit fresh read')
                    assert stored['status'] == ('published' if case == 'normal' else 'review')
                    rows = sql('SELECT claim FROM publish_write_intents WHERE task_id=?', (tid,))
                    assert len(rows) == (stages if case == 'normal' else target)
                    assert all(r[0] == owners[0] for r in rows)
                    owner_after = stored['execution_claim']
                    for _ in range(3):
                        assert not execution.execute_autonomous_publish_task(tid, asset_resolver=Resolver())['executed']
                    assert len(transport.writes) == expected
                    assert manager.get_publish_task(tid)['execution_claim'] == owner_after
                    assert sql('SELECT claim FROM publish_write_intents WHERE task_id=?', (tid,)) == rows
                    update_autonomy_settings(autonomy_enabled=True, kill_switch_active=False)
    print('G5_POST_INTENT_ALL_PROVIDER_STAGES=PASS')
    print('G5_POST_INTENT_CASES=70')


def main():
    manager._init_db()
    update_autonomy_settings(autonomy_enabled=True, kill_switch_active=False)
    post_intent_checks()
    # Actual adapter transport contracts, canonical worker, persisted correlation.
    for platform, count in [('youtube', 2), ('instagram', 2), ('facebook', 3)]:
        with ExitStack() as stack:
            payload, transport, token, adapter, result = environment(stack, platform)
            tid = task(payload)
            queue = PublishQueue(); queue.add_task(tid)
            resolver = Resolver()
            PublishWorker(queue, asset_resolver=resolver).run_once()
            stored = manager.get_publish_task(tid)
            assert stored['status'] == 'published', stored
            assert stored['video_id'] == result['video_id'] and stored['platform_video_id']
            assert stored['provider_operation_id'] and stored['provider_operation_status'] == 'PUBLISHED'
            assert len(transport.writes) == count
            for _ in range(3):
                assert execution.execute_autonomous_publish_task(tid)['executed'] is False
            assert len(transport.writes) == count
            assert policy.prepare_autonomous_publish_task(payload)['policy']['decision'] == 'BLOCK'
            assert sql('SELECT COUNT(*) FROM publish_tasks WHERE asset_id=?', (payload['asset_id'],))[0][0] == 1
            if platform == 'youtube':
                assert resolver.cleaned == 1
            if platform == 'facebook':
                assert transport.reads == []
            print(f'G5_{platform.upper()}_CANONICAL_OFFLINE=PASS')

    # Policy failure matrix: no task, no external write for each hard/unknown input.
    for case in ['quality', 'missing_asset', 'wrong_platform', 'expired', 'missing_scope', 'disconnected',
                 'adapter_disabled', 'kill', 'disabled', 'future', 'unknown_expiry', 'credential_provider']:
        with ExitStack() as stack:
            payload, transport, token, adapter, result = environment(stack)
            if case == 'quality':
                sql("UPDATE asset_quality_checks SET status='REVIEW' WHERE production_result_id=?", (result['id'],))
            if case == 'missing_asset': payload['asset_id'] = 'missing'
            if case == 'wrong_platform': payload['platform'] = 'facebook'
            if case == 'expired': token['expires_at'] = (policy.now() - timedelta(hours=1)).isoformat()
            if case == 'missing_scope': token['scopes'] = []
            if case == 'disconnected': sql("UPDATE accounts SET status='disconnected' WHERE id=?", (payload['account_id'],))
            if case == 'adapter_disabled': adapter.live_publish_enabled = False
            if case == 'kill': update_autonomy_settings(kill_switch_active=True)
            if case == 'disabled': update_autonomy_settings(autonomy_enabled=False)
            if case == 'future': payload['scheduled_time'] = (policy.now() + timedelta(hours=1)).isoformat()
            if case == 'unknown_expiry': token['expires_at'] = None
            if case == 'credential_provider': token['provider'] = 'wrong-provider'
            before = sql('SELECT COUNT(*) FROM publish_tasks')[0][0]
            denied = policy.prepare_autonomous_publish_task(payload)
            assert denied['policy']['decision'] in {'REVIEW', 'BLOCK'} and not denied['created'], case
            if case in {'disabled', 'future', 'unknown_expiry'}:
                assert denied['policy']['decision'] == 'REVIEW', case
            else:
                assert denied['policy']['decision'] == 'BLOCK', case
            assert sql('SELECT COUNT(*) FROM publish_tasks')[0][0] == before and not transport.writes
            update_autonomy_settings(autonomy_enabled=True, kill_switch_active=False)
    print('G5_FAILURE_POLICY_MATRIX=PASS')

    # Default autonomous YouTube staging uses the canonical publish resolver.
    with ExitStack() as stack:
        payload, transport, *_ = environment(stack, 'youtube')
        resolver = Resolver()
        calls = []
        from publish.asset_resolver import AssetResolver
        def prepare(self, asset):
            calls.append((asset['asset_url'], asset['storage_type']))
            return resolver.prepare(asset)
        stack.enter_context(patch.object(AssetResolver, 'prepare', prepare))
        tid = task(payload)
        assert execute_publish_task(tid)['task']['status'] == 'published'
        assert len(calls) == 1 and calls[0][1] == 'github_pages'
    print('G5_CANONICAL_PUBLISH_RESOLVER=PASS')

    for platform in ('youtube', 'facebook'):
        with ExitStack() as stack:
            payload, transport, *_ = environment(stack, platform)
            transport.upload_destination = 'https://attacker.invalid/upload'
            tid = task(payload)
            execution.execute_autonomous_publish_task(tid, asset_resolver=Resolver())
            assert manager.get_publish_task(tid)['status'] == 'review' and len(transport.writes) == 1
    with ExitStack() as stack:
        payload, transport, *_ = environment(stack, 'facebook')
        transport.acknowledged = False
        tid = task(payload)
        assert execute_publish_task(tid)['task']['status'] == 'review' and len(transport.writes) == 2
    print('G5_PROVIDER_DESTINATION_AND_ACK_GUARD=PASS')

    with ExitStack() as stack:
        payload, transport, token, *_ = environment(stack)
        first = task(payload)
        other = fixture.evaluate(fixture.source())
        assert policy.prepare_autonomous_publish_task({**payload, 'asset_id': other['asset_id']})['policy']['decision'] == 'BLOCK'
        # Three spaced same-day published tasks, last beyond min interval => daily gate.
        sql('DELETE FROM publish_tasks WHERE id=?', (first,))
        for hours in [2, 4, 6]:
            sql("INSERT INTO publish_tasks(asset_id,platform,account_id,status,created_at) VALUES(?,?,?,'published',?)",
                (f'history-{hours}', payload['platform'], payload['account_id'], policy.now().replace(hour=12).isoformat()))
        token['expires_at'] = (policy.now() + timedelta(days=1)).isoformat()
        with patch.object(policy, 'now', lambda: policy.datetime.now(policy.timezone.utc).replace(hour=18)):
            denied = policy.prepare_autonomous_publish_task(payload)
            assert 'DAILY_MAXIMUM' in denied['policy']['reason_codes']
            assert 'MINIMUM_INTERVAL' not in denied['policy']['reason_codes']
    print('G5_CADENCE_AND_DAILY_LIMIT=PASS')

    # Response lost after every possible provider POST: never resend any stage.
    for platform, writes in [('youtube', 1), ('instagram', 2), ('facebook', 3)]:
        for stage in range(1, writes + 1):
            with ExitStack() as stack:
                payload, transport, *_ = environment(stack, platform, fail_at=stage)
                tid = task(payload)
                execution.execute_autonomous_publish_task(tid, asset_resolver=Resolver())
                assert manager.get_publish_task(tid)['status'] == 'review'
                assert len(transport.writes) == stage
                execution.reconcile_autonomous_publish_task(tid)
                execution.execute_autonomous_publish_task(tid, asset_resolver=Resolver())
                assert len(transport.writes) == stage
    print('G5_POST_AMBIGUITY_NO_RETRY=PASS')

    # Kill flipped after container POST; media_publish must never run.
    with ExitStack() as stack:
        payload, transport, *_ = environment(stack, hook=lambda n: update_autonomy_settings(kill_switch_active=True))
        tid = task(payload)
        execution.execute_autonomous_publish_task(tid)
        assert len(transport.writes) == 1 and manager.get_publish_task(tid)['status'] == 'review'
        update_autonomy_settings(kill_switch_active=False)
    print('G5_FRESH_CONTROL_CHECK=PASS')

    with ExitStack() as stack:
        payload, transport, *_ = environment(stack)
        tid = task(payload)
        sql("UPDATE publish_tasks SET execution_claim='lost-owner',status='publishing',execution_started_at='2000-01-01T00:00:00',updated_at='2000-01-01T00:00:00' WHERE id=?", (tid,))
        execution.execute_autonomous_publish_task(tid)
        assert execution.reconcile_autonomous_publish_task(tid)['status'] == 'review' and not transport.writes
    print('G5_STALE_OWNER_FAIL_CLOSED=PASS')

    # Real crash windows: committed intent but no response, and saved response
    # but no final task status. Reconciliation never calls the provider again.
    for platform in ('youtube', 'instagram', 'facebook'):
        with ExitStack() as stack:
            payload, transport, *_ = environment(stack, platform)
            tid = task(payload)
            with patch.object(execution, '_finish', side_effect=SimulatedCrash):
                try:
                    execution.execute_autonomous_publish_task(tid, asset_resolver=Resolver())
                except SimulatedCrash:
                    pass
                else:
                    raise AssertionError('crash hook not reached')
            writes = len(transport.writes)
            assert manager.get_publish_task(tid)['status'] == 'publishing'
            sql("UPDATE publish_tasks SET updated_at='2000-01-01T00:00:00' WHERE id=?", (tid,))
            recovered = execution.reconcile_autonomous_publish_task(tid)
            assert recovered['status'] == 'published' and recovered['platform_video_id']
            assert not execute_publish_task(tid)['executed'] and len(transport.writes) == writes
            execution.reconcile_autonomous_publish_task(tid)
            assert sum(json.loads(r[0]).get('publish_task_id') == tid for r in sql("SELECT payload FROM events WHERE event_type='publish.completed'")) == 1
    with ExitStack() as stack:
        def crash(_):
            raise SimulatedCrash()
        payload, transport, *_ = environment(stack, hook=crash)
        tid = task(payload)
        try:
            execution.execute_autonomous_publish_task(tid)
        except SimulatedCrash:
            pass
        else:
            raise AssertionError('POST-before-persistence crash not reached')
        assert len(transport.writes) == 1 and not sql('SELECT * FROM publish_operation_events WHERE task_id=?', (tid,))
        assert execution.reconcile_autonomous_publish_task(tid)['status'] == 'publishing'  # fresh owner untouched
        sql("UPDATE publish_tasks SET updated_at='2000-01-01T00:00:00' WHERE id=?", (tid,))
        assert execution.reconcile_autonomous_publish_task(tid)['status'] == 'review'
        assert not execute_publish_task(tid)['executed'] and len(transport.writes) == 1
    print('G5_CRASH_RESPONSE_CORRELATION_RECOVERY=PASS')

    with ExitStack() as stack:
        payload, transport, *_ = environment(stack)
        transport.terminal_failure = True
        tid = task(payload)
        assert execute_publish_task(tid)['task']['status'] == 'review'
        assert len(transport.writes) == 1 and not execute_publish_task(tid)['executed']
    print('G5_PROVIDER_TERMINAL_FAILURE=PASS')

    for mutation in ('payload', 'source', 'kill'):
        with ExitStack() as stack:
            payload, transport, token, adapter, result = environment(stack)
            tid = task(payload)
            if mutation == 'payload': sql("UPDATE publish_tasks SET title='changed' WHERE id=?", (tid,))
            if mutation == 'source': sql("UPDATE production_results SET output='{}' WHERE id=?", (result['id'],))
            if mutation == 'kill': update_autonomy_settings(kill_switch_active=True)
            assert execute_publish_task(tid)['task']['status'] == 'review' and not transport.writes
            assert manager.claim_publish_task(tid) is False
            update_autonomy_settings(kill_switch_active=False)
    print('G5_STALE_TASK_SOURCE_REJECTION=PASS')

    q = PublishQueue()
    due = (policy.now() - timedelta(seconds=1)).isoformat()
    future = (policy.now() + timedelta(hours=1)).isoformat()
    PublishScheduler(q).check([{'id': 1, 'status': 'pending', 'scheduled_time': due},
                              {'id': 2, 'status': 'pending', 'scheduled_time': future},
                              {'id': 3, 'status': 'review', 'scheduled_time': due}])
    assert q.get_pending_tasks() == [1]
    print('G5_SCHEDULER_WINDOW=PASS')

    for round_number in range(20):
        with ExitStack() as stack:
            platform = ('youtube', 'instagram', 'facebook')[round_number % 3]
            payload, transport, *_ = environment(stack, platform)
            expected_writes = 3 if platform == 'facebook' else 2
            resolver = Resolver()
            with ThreadPoolExecutor(max_workers=4) as pool:
                prepared = list(pool.map(lambda _: policy.prepare_autonomous_publish_task(payload), range(4)))
            assert sum(r['created'] for r in prepared) == 1
            tid = next(r['task']['id'] for r in prepared if r['created'])
            with ThreadPoolExecutor(max_workers=4) as pool:
                executed = list(pool.map(lambda _: execution.execute_autonomous_publish_task(tid, asset_resolver=resolver), range(4)))
            assert sum(r['executed'] for r in executed) == 1
            assert len(transport.writes) == expected_writes and manager.get_publish_task(tid)['status'] == 'published'
            assert sql('SELECT COUNT(*) FROM publish_tasks WHERE asset_id=?', (payload['asset_id'],))[0][0] == 1
            assert sql('SELECT COUNT(*) FROM publish_write_intents WHERE task_id=?', (tid,))[0][0] == expected_writes
            # DB uniqueness is real, not just service-level create-or-get.
            try:
                sql("INSERT INTO publish_tasks(asset_id,platform,account_id,status,autonomous_policy_version) VALUES(?,?,?,'failed','g5-v1')",
                    (payload['asset_id'], platform, payload['account_id']))
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError('Canonical identity index missing')
    print('G5_CONCURRENCY_ROUNDS=20\nG5_ONE_TASK_ONE_WRITE_OWNER=PASS')

    with ExitStack() as stack:
        payload, transport, *_ = environment(stack)
        tid = task(payload)
        sql('DROP INDEX uq_publish_active_identity')
        sql("INSERT INTO publish_tasks(asset_id,platform,account_id,status) VALUES(?,?,?,'pending')",
            (payload['asset_id'], payload['platform'], payload['account_id']))
        assert policy.prepare_autonomous_publish_task(payload)['policy']['decision'] == 'BLOCK'
        execution.execute_autonomous_publish_task(tid)
        assert not transport.writes
        assert sql('SELECT COUNT(*) FROM publish_tasks WHERE asset_id=?', (payload['asset_id'],))[0][0] == 2
    print('G5_LEGACY_DUPLICATES_PRESERVED=PASS')
    data = sql('SELECT policy_evidence,error_message,provider_operation_id,provider_operation_status FROM publish_tasks')
    assert SECRET not in str(data)
    print('G5_SECRET_PERSISTENCE_LEAK=0\nREAL_PLATFORM_WRITE_COUNT=0\nG5_OFFLINE_CERTIFICATION=PASS')


if __name__ == '__main__':
    try:
        captured = io.StringIO()
        with redirect_stdout(captured), redirect_stderr(captured), patch.object(socket.socket, 'connect', blocked), patch.object(socket, 'getaddrinfo', blocked):
            main()
        assert SECRET not in captured.getvalue()
        print(captured.getvalue(), end='')
    finally:
        gc.collect()
        fixture.TEMP.cleanup()
