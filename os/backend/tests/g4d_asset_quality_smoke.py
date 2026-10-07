"""G4-D certification: real service/SQLite, fake DNS/HTTP/media probe only."""
import copy
import gc
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'os/backend'))
TEMP = tempfile.TemporaryDirectory(prefix='g4d-offline-')
DB = Path(TEMP.name) / 'os.db'
os.environ.update(OS_TESTING='1', OS_DATABASE_PATH=str(DB))

from assets import quality, remote_media
from assets.binding import create_asset_from_result
from assets.manager import _init_db, create_video_asset
from assets.remote_media import RemoteMedia, MediaProbe, MediaFailure
from production.tasks.manager import create_task, update_task_status
from production.tasks.scheduler import schedule_task
from production.runtime.manager import update_job_status
from production.results.manager import create_or_get_result_for_job, get_result

SENTINEL = 'SECRET_SENTINEL'
URL = 'https://cdn.example/video.mp4?token=' + SENTINEL
GOOD_PROBE = {'format': {'format_name': 'mov,mp4,m4a,3gp,3g2,mj2', 'duration': '45'},
              'streams': [{'codec_type': 'video', 'codec_name': 'h264', 'width': 720, 'height': 1280},
                          {'codec_type': 'audio', 'codec_name': 'aac'}]}


def blocked(*a, **k):
    raise AssertionError('real network or probe forbidden')


def public_dns(host, port, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', port))]


def private_dns(host, port, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.1.2.3', port))]


def mixed_dns(host, port, **kwargs):
    return public_dns(host, port) + private_dns(host, port)


def failed_dns(*a, **k):
    raise socket.gaierror('temporary ' + SENTINEL)


class Response:
    def __init__(self, *, status=200, mime='video/mp4', size=65536, headers=None, error=None):
        self.status_code = status
        self.headers = {'Content-Type': mime, **(headers or {})}
        self.size, self.error, self.closed = size, error, False

    def iter_content(self, chunk_size):
        if self.error:
            raise self.error
        remaining = self.size
        while remaining:
            size = min(chunk_size, remaining)
            yield b'x' * size
            remaining -= size

    def close(self):
        self.closed = True


class Session:
    def __init__(self, responses=None, error=None):
        self.responses = responses or [Response()]
        self.error = error
        self.calls = 0
        self.lock = threading.Lock()

    def get(self, url, *, host, addresses, timeout, allow_redirects):
        assert allow_redirects is False and timeout == (5, 30)
        assert addresses == ['93.184.216.34']
        with self.lock:
            index = self.calls
            self.calls += 1
        if self.error:
            raise self.error
        return self.responses[min(index, len(self.responses) - 1)]


class Probe:
    def __init__(self, data=None, error=None):
        self.data = copy.deepcopy(GOOD_PROBE if data is None else data)
        self.error, self.calls, self.paths = error, 0, []
        self.lock = threading.Lock()

    def inspect(self, path):
        assert path.is_file() and not path.resolve().is_relative_to(ROOT)
        with self.lock:
            self.calls += 1
            self.paths.append(path)
        if self.error:
            raise self.error
        return self.data


def source(provider='github', url=URL, status='completed', legacy=False):
    task = create_task({'provider': provider, 'task_type': 'video_generation' if provider == 'ai_gateway' else 'video_batch',
                        'workflow': 'render-short01.yml' if provider == 'github' else '',
                        'parameters': {'content_id': 'g4d-fixture'}})
    job = schedule_task(task)
    update_task_status(task.id, status)
    update_job_status(job['id'], status)
    output = {'asset_url': url, 'storage_type': 'github_pages' if provider == 'github' else 'ai_output',
              'g4b_no_asset_binding' if legacy else 'defer_asset_binding': True,
              'github_run_id' if provider == 'github' else 'remote_job_id': 'offline-correlation'}
    return create_or_get_result_for_job({'runtime_job_id': job['id'], 'video_id': 'g4d-fixture',
                                        'provider': provider, 'status': status, 'output': output})


def count(table, rid):
    with sqlite3.connect(DB) as db:
        return db.execute(f'SELECT COUNT(*) FROM {table} WHERE production_result_id=?', (str(rid),)).fetchone()[0]


def evaluate(row, *, session=None, resolver=public_dns, probe=None, **kwargs):
    return quality.evaluate_production_result_asset(row['id'], downloader=RemoteMedia(session=session or Session(), resolver=resolver),
                                                   probe=probe or Probe(), **kwargs)


def rejected(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError('expected fail-closed rejection')


def main():
    assert DB.resolve() != (ROOT / 'os/database/os.db').resolve()
    _init_db()
    quality.init_quality_table()
    # Exercise the real connection implementation with fake socket/TLS. DNS
    # is globally blocked, so a second hostname lookup would fail this proof.
    class FakeSocket:
        def settimeout(self, value):
            self.timeout = value
        def connect(self, address):
            self.address = address
        def close(self):
            pass
    sock = FakeSocket()
    tls_names = []
    class FakeTLS:
        check_hostname = True
        verify_mode = 2
        def wrap_socket(self, value, *, server_hostname):
            tls_names.append(server_hostname)
            return value
    with patch.object(remote_media.socket, 'socket', return_value=sock), \
            patch.object(remote_media.ssl, 'create_default_context', return_value=FakeTLS()):
        connection = remote_media._PinnedConnection('cdn.example', '93.184.216.34', 5)
        connection.connect()
        assert sock.address == ('93.184.216.34', 443) and tls_names == ['cdn.example']
        connection.close()
    print('G4D_DNS_PINNED_CONNECTION=PASS')
    with patch.object(remote_media.shutil, 'which', return_value='fake-ffprobe'), \
            patch.object(remote_media.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(GOOD_PROBE))) as run:
        assert MediaProbe().inspect(Path('offline.mp4')) == GOOD_PROBE
        assert run.call_args.kwargs['shell'] is False and run.call_args.kwargs['timeout'] == 30
        assert '-protocol_whitelist' in run.call_args.args[0] and '-format_whitelist' in run.call_args.args[0]
    print('G4D_PROBE_ARGUMENT_LIST_NO_NETWORK=PASS')
    for provider in ('github', 'ai_gateway'):
        row = source(provider, legacy=provider == 'github')
        original = get_result(row['id'])['output']
        session, probe = Session(), Probe()
        decision = evaluate(row, session=session, probe=probe)
        assert decision['status'] == 'PASS'
        assert decision['asset_id'] == f"asset-result-{row['id']}"
        assert count('asset_quality_checks', row['id']) == count('video_assets', row['id']) == 1
        persisted = get_result(row['id'])
        assert persisted['status'] == 'completed' and persisted['output'] == original
        assert persisted['asset_id'] == decision['asset_id'] and persisted['asset_status'] == 'ready'
        with sqlite3.connect(DB) as db:
            db.row_factory = sqlite3.Row
            asset = db.execute('SELECT * FROM video_assets WHERE asset_id=?', (decision['asset_id'],)).fetchone()
            assert asset['source_provider'] == provider
            assert asset['storage_type'] == ('github_pages' if provider == 'github' else 'ai_output')
            assert asset['asset_url'] == URL and asset['file_path'] is None
            metadata = json.loads(asset['metadata'])
            assert metadata['quality_check_id'] == decision['id'] and metadata['quality_decision'] == 'PASS'
            assert SENTINEL not in asset['metadata']
        for _ in range(3):
            replay = evaluate(row, session=session, probe=probe)
            assert replay['asset_id'] == decision['asset_id'] and replay['id'] == decision['id']
        assert session.calls == probe.calls == 1
        assert all(not path.exists() for path in probe.paths)
        if provider == 'ai_gateway':
            from production.results.manager import persist_deferred_ai_response
            replay = persist_deferred_ai_response(row['runtime_job_id'], {'status': 'completed', 'output': original}, recovery=True)
            assert replay['asset_id'] == decision['asset_id'] and replay['output'] == original
        print('G4D_GITHUB_PROVIDER_PASS=PASS' if provider == 'github' else 'G4D_AI_PROVIDER_PASS=PASS')
    print('G4D_UNIFIED_GATE=PASS')
    print('G4D_PASS_REPLAY_IDEMPOTENT=PASS')
    print('G4D_RESULT_ASSET_BINDING=PASS')
    print('G4D_G4C_TERMINAL_REPLAY_AFTER_BINDING=PASS')
    row = source()
    silent = copy.deepcopy(GOOD_PROBE)
    silent['streams'] = silent['streams'][:1]
    octet = evaluate(row, session=Session([Response(mime='application/octet-stream')]), probe=Probe(data=silent))
    assert octet['status'] == 'PASS' and octet['evidence']['audio_stream_present'] is False
    assert evaluate(source('ai_gateway'), session=Session([Response(mime='application/octet-stream')]))['status'] == 'BLOCK'
    print('G4D_AUDIO_EVIDENCE=PASS')
    print('G4D_OCTET_STREAM_REQUIRES_GITHUB_AND_PROBE=PASS')
    dns_hosts = []
    def tracking_dns(host, port, **kwargs):
        dns_hosts.append(host)
        return public_dns(host, port)
    redirected = evaluate(source(), resolver=tracking_dns, session=Session([
        Response(status=302, headers={'Location': 'https://second.example/media.mp4'}), Response()]))
    assert redirected['status'] == 'PASS' and dns_hosts == ['cdn.example', 'second.example']
    print('G4D_REDIRECT_REVALIDATION=PASS')

    # Both helper and lower-level registry reject deferred shortcuts.
    row = source()
    assert not create_asset_from_result(row)['asset_id']
    rejected(lambda: create_video_asset({'asset_id': 'bypass', 'video_id': 'g4d-fixture',
                                         'production_result_id': str(row['id']), 'source_provider': 'github',
                                         'asset_url': URL, 'status': 'ready'}))
    assert count('video_assets', row['id']) == 0
    print('G4D_LEGACY_SHORTCUT_BLOCKED=PASS')

    # A failed/running/submitted production cannot become quality PASS.
    for status in ('failed', 'running', 'submitted'):
        row = source(status=status)
        rejected(lambda: evaluate(row))
        assert count('asset_quality_checks', row['id']) == count('video_assets', row['id']) == 0
    print('G4D_TERMINAL_RESULT_REQUIRED=PASS')

    cases = [
        ('MISSING_URL', {'url': None}, {}),
        ('HTTP_URL', {'url': 'http://public.example/video.mp4'}, {}),
        ('PRIVATE_IP', {'url': 'https://127.0.0.1/video.mp4'}, {}),
        ('LOCALHOST', {'url': 'https://localhost/video.mp4'}, {}),
        ('PRIVATE_DNS', {}, {'resolver': private_dns}),
        ('MIXED_DNS', {}, {'resolver': mixed_dns}),
        ('PORT', {'url': 'https://cdn.example:8443/video.mp4'}, {}),
        ('CREDENTIAL_URL', {'url': 'https://user:pass@cdn.example/video.mp4'}, {}),
        ('REDIRECT_PRIVATE', {}, {'session': Session([Response(status=302, headers={'Location': 'https://10.0.0.1/video.mp4'})])}),
        ('REDIRECT_HTTP', {}, {'session': Session([Response(status=302, headers={'Location': 'http://cdn.example/video.mp4'})])}),
        ('REDIRECT_CREDENTIAL', {}, {'session': Session([Response(status=302, headers={'Location': 'https://u:p@cdn.example/video.mp4'})])}),
        ('REDIRECT_LIMIT', {}, {'session': Session([Response(status=302, headers={'Location': '/again'})])}),
        ('HTML', {}, {'session': Session([Response(mime='text/html')])}),
        ('EMPTY', {}, {'session': Session([Response(size=0)])}),
        ('TOO_SMALL', {}, {'session': Session([Response(size=1024)])}),
        ('TOO_LARGE', {}, {'session': Session([Response(headers={'Content-Length': str(remote_media.MAX_BYTES + 1)})])}),
        ('ENCODING', {}, {'session': Session([Response(headers={'Content-Encoding': 'gzip'})])}),
        ('INVALID_MEDIA', {}, {'probe': Probe(data={'bad': True})}),
        ('NO_VIDEO_STREAM', {}, {'probe': Probe(data={'format': GOOD_PROBE['format'], 'streams': []})}),
    ]
    for value in ('0', '1', '181', 'NaN', 'Infinity'):
        data = copy.deepcopy(GOOD_PROBE)
        data['format']['duration'] = value
        cases.append(('BAD_DURATION_' + value, {}, {'probe': Probe(data=data)}))
    for width, height in ((0, 1280), (320, 568), (1280, 720)):
        data = copy.deepcopy(GOOD_PROBE)
        data['streams'][0].update(width=width, height=height)
        cases.append(('BAD_DIMENSIONS_ASPECT_' + str(width), {}, {'probe': Probe(data=data)}))
    for name, args, opts in cases:
        row = source(**args)
        decision = evaluate(row, **opts)
        assert decision['status'] == 'BLOCK', (name, decision['reason_codes'])
        assert count('video_assets', row['id']) == 0
        assert get_result(row['id'])['status'] == 'completed'
        replay_session, replay_probe = Session(), Probe()
        replay = evaluate(row, session=replay_session, probe=replay_probe)
        assert replay['id'] == decision['id'] and replay['status'] == 'BLOCK'
        assert replay_session.calls == replay_probe.calls == 0
        print('G4D_' + name.upper() + '_BLOCK=PASS')
    print('G4D_BLOCK_REPLAY_IDEMPOTENT=PASS')

    # Streaming bounds are checked even when Content-Length is absent.
    row = source()
    response = Response(size=65536)
    with patch.object(remote_media, 'MAX_BYTES', 40000):
        assert evaluate(row, session=Session([response]))['status'] == 'BLOCK'
    assert response.closed and count('video_assets', row['id']) == 0
    print('G4D_STREAMING_SIZE_GATE=PASS')

    # A progressing transfer may exceed the old 120-second limit while
    # remaining inside the bounded 600-second download budget.
    row = source()
    slow_clock = iter((0.0, 121.0))
    with patch.object(remote_media.time, 'monotonic', side_effect=lambda: next(slow_clock)):
        slow = evaluate(row, session=Session([Response(size=65536)]), probe=Probe())
    assert slow['status'] == 'PASS'
    assert count('video_assets', row['id']) == 1
    print('G4D_SLOW_PROGRESS_OVER_120=PASS')

    # A transfer that exceeds the total bounded budget is a review outcome,
    # and must not create an asset.
    row = source()
    timeout_clock = iter((0.0, 601.0))
    with patch.object(remote_media.time, 'monotonic', side_effect=lambda: next(timeout_clock)):
        timed_out = evaluate(row, session=Session([Response(size=65536)]), probe=Probe())
    assert timed_out['status'] == 'REVIEW'
    assert 'DOWNLOAD_TIMEOUT' in timed_out['reason_codes']
    assert count('video_assets', row['id']) == 0
    print('G4D_TOTAL_TIMEOUT_OVER_600=PASS')

    # All transient outcomes retain the same quality row and can later PASS.
    for opts in ({'session': Session(error=socket.timeout(SENTINEL))},
                 {'session': Session([Response(status=503)])},
                 {'resolver': failed_dns},
                 {'probe': Probe(error=MediaFailure('REVIEW', 'FFPROBE_UNAVAILABLE'))}):
        row = source()
        decision = evaluate(row, **opts)
        assert decision['status'] == 'REVIEW' and count('video_assets', row['id']) == 0
        passed = evaluate(row)
        assert passed['status'] == 'PASS' and passed['id'] == decision['id']
        assert passed['attempts'] == 2 and count('video_assets', row['id']) == 1
    print('G4D_REVIEW_RETRY_TO_PASS=PASS')

    # Exception cleanup after download, including exceptions raised by probe.
    row = source()
    probe = Probe(error=RuntimeError(SENTINEL))
    assert evaluate(row, probe=probe)['status'] == 'REVIEW'
    assert probe.paths and all(not p.exists() for p in probe.paths)
    print('G4D_TEMP_EXCEPTION_CLEANUP=PASS')
    for failure in (None, subprocess.TimeoutExpired('ffprobe', 30)):
        with patch.object(remote_media.shutil, 'which', return_value=None if failure is None else 'fake-ffprobe'), \
                patch.object(remote_media.subprocess, 'run', side_effect=failure or blocked):
            try:
                MediaProbe().inspect(Path('never-opened'))
            except MediaFailure as exc:
                assert exc.decision == 'REVIEW'
            else:
                raise AssertionError('unavailable probe passed')
    print('G4D_PROBE_UNAVAILABLE_REVIEW=PASS')

    row = source()
    evaluate(row, session=Session(error=socket.timeout()))
    with sqlite3.connect(DB) as db:
        altered = dict(row['output'], asset_url='https://cdn.example/changed.mp4')
        db.execute('UPDATE production_results SET output=? WHERE id=?', (json.dumps(altered), row['id']))
    rejected(lambda: evaluate(row))
    assert count('video_assets', row['id']) == 0
    print('G4D_SOURCE_DRIFT_FAIL_CLOSED=PASS')

    row = source()
    def crash():
        raise RuntimeError('simulated interruption')
    try:
        evaluate(row, before_binding=crash)
    except RuntimeError:
        pass
    else:
        raise AssertionError('missing crash')
    assert count('video_assets', row['id']) == 0 and get_result(row['id'])['asset_id'] is None
    assert evaluate(row)['status'] == 'PASS' and count('video_assets', row['id']) == 1
    print('G4D_ATOMIC_FINALIZATION_CRASH_RECOVERY=PASS')

    for round_no in range(20):
        row = source('github' if round_no % 2 == 0 else 'ai_gateway')
        barrier = threading.Barrier(4)
        def call(_):
            barrier.wait(timeout=10)
            return evaluate(row)
        with ThreadPoolExecutor(max_workers=4) as pool:
            decisions = list(pool.map(call, range(4)))
        assert all(d['status'] == 'PASS' for d in decisions)
        assert len({d['id'] for d in decisions}) == len({d['asset_id'] for d in decisions}) == 1
        assert count('asset_quality_checks', row['id']) == count('video_assets', row['id']) == 1
        assert get_result(row['id'])['asset_id'] == decisions[0]['asset_id']
    print('G4D_CONCURRENCY_ROUNDS=20')
    print('G4D_FINALIZATION_AT_MOST_ONCE=PASS')

    # Preserve old duplicate history, never choose a latest row or delete one.
    row = source()
    with sqlite3.connect(DB) as db:
        db.execute('DROP INDEX uq_video_assets_production_result')
        for aid in ('old-a', 'old-b'):
            db.execute('INSERT INTO video_assets(asset_id,production_result_id) VALUES(?,?)', (aid, str(row['id'])))
    rejected(lambda: evaluate(row))
    assert count('video_assets', row['id']) == 2
    print('G4D_LEGACY_DUPLICATE_ASSET_FAIL_CLOSED=PASS')
    row = source()
    evaluate(row, session=Session(error=socket.timeout()))
    with sqlite3.connect(DB) as db:
        db.execute('DROP INDEX uq_asset_quality_result')
        db.execute('''INSERT INTO asset_quality_checks(production_result_id,policy_version,source_fingerprint,status,reason_codes,evidence,created_at,updated_at)
            SELECT production_result_id,policy_version,source_fingerprint,status,reason_codes,evidence,created_at,updated_at
            FROM asset_quality_checks WHERE production_result_id=?''', (row['id'],))
    rejected(lambda: evaluate(row))
    assert count('asset_quality_checks', row['id']) == 2 and count('video_assets', row['id']) == 0
    print('G4D_DUPLICATE_QUALITY_FAIL_CLOSED=PASS')
    with sqlite3.connect(DB) as db:
        records = db.execute('SELECT evidence,reason_codes FROM asset_quality_checks').fetchall()
        assert SENTINEL not in json.dumps(records)
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='publish_tasks'").fetchone():
            assert db.execute('SELECT COUNT(*) FROM publish_tasks').fetchone()[0] == 0
    print('G4D_SECRET_EVIDENCE_LEAK=0')
    print('G4D_PUBLISH_TASK_COUNT=0')
    print('REAL_MEDIA_HTTP_GET_COUNT=0')
    print('REAL_MEDIA_HTTP_HEAD_COUNT=0')
    print('G4D_ASSET_QUALITY_SMOKE=PASS')


if __name__ == '__main__':
    try:
        captured = io.StringIO()
        with redirect_stdout(captured), redirect_stderr(captured), \
                patch.object(socket.socket, 'connect', blocked), patch.object(socket, 'getaddrinfo', blocked), \
                patch.object(subprocess, 'run', blocked):
            main()
        assert SENTINEL not in captured.getvalue()
        print(captured.getvalue(), end='')
        print('G4D_SECRET_LOG_LEAK=0')
    finally:
        gc.collect()
        TEMP.cleanup()
