"""Canonical G4-C offline proof. Fake HTTP only; unique external TEMP DB."""
import gc
import json
import os
import socket
import sqlite3
import sys
import threading
import io
from contextlib import redirect_stdout, redirect_stderr
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g4a_authorized_production_smoke as fixture
from ai.gateway import AIGatewayService
from ai.models import AIRequest
from ai.providers.video import VideoProvider
from intelligence import autonomy, policy
from orchestration.production import prepare_authorized_production, claim_authorized_production_execution
from production.providers.ai_gateway import AIGatewayProvider
from production.runtime import orchestrator as runtime
from production.runtime.manager import get_job
from production.results.manager import get_results

SECRET = 'g4c-secret-sentinel-never-persist'
ENDPOINT = 'https://gateway.example.test/video'
ASSET = 'https://cdn.example.test/video.mp4'


def blocked(*args, **kwargs):
    raise AssertionError('real network forbidden')


class Response:
    status_code = 200

    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(SECRET)

    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


class Session:
    def __init__(self):
        self.posts = 0
        self.gets = 0
        self.lock = threading.Lock()
        self.post_data = {'status': 'submitted', 'job_id': 'remote-1', 'poll_url': '/jobs/1'}
        self.get_data = {'status': 'completed', 'asset_url': ASSET}
        self.before_network = None
        self.sent = None

    def post(self, url, **kwargs):
        with self.lock:
            self.posts += 1
        assert kwargs['allow_redirects'] is False
        assert kwargs['headers']['Authorization'] == 'Bearer ' + SECRET
        self.sent = kwargs
        if self.before_network:
            self.before_network(kwargs)
        if isinstance(self.post_data, Exception):
            raise self.post_data
        return Response(self.post_data)

    def get(self, url, **kwargs):
        with self.lock:
            self.gets += 1
        assert url.startswith('https://gateway.example.test:443/')
        assert kwargs['allow_redirects'] is False
        if isinstance(self.get_data, Exception):
            raise self.get_data
        return Response(self.get_data)


def provider(session=None, endpoint=ENDPOINT):
    session = session or Session()
    gateway = AIGatewayService()
    gateway.providers['video'] = VideoProvider(endpoint=endpoint, api_key=SECRET, session=session)
    return AIGatewayProvider(gateway), session


def claimed(tag, review=False):
    fixture._enable()
    os.environ['OS_PRODUCTION_PROVIDER'] = 'ai_gateway'
    pid = fixture._create('c-' + tag)
    if review:
        gates = {k: 'PASS' for k in ('safety', 'novelty', 'duplicate_risk', 'account_health', 'platform_health', 'ai_confidence')}
        gates['business'] = 'UNKNOWN'
        assert policy.evaluate_policy(pid, gates)['decision'] == 'REVIEW'
        autonomy.set_policy_override(pid, 'AUTO', 'isolated fixture authorization')
    prepare_authorized_production(pid)
    row = claim_authorized_production_execution(pid)
    return pid, row['runtime_job']['id']


def rejected(call):
    try:
        call()
    except (ValueError, RuntimeError):
        return
    raise AssertionError('expected fail-closed rejection')


def main():
    assert fixture.DB.resolve() != (fixture.ROOT / 'os/database/os.db').resolve()
    os.environ['OS_AI_VIDEO_AUTONOMOUS_EXECUTION_ENABLED'] = 'true'
    pid, jid = claimed('happy')
    p, http = provider()
    def intent_check(kwargs):
        intent = json.loads(get_job(jid)['execution_metadata'])
        assert get_job(jid)['execution_state'] == 'dispatch_intent'
        assert intent['request_id'] == kwargs['headers']['Idempotency-Key'] == f'g4c-runtime-job-{jid}'
        assert len(intent['endpoint_fingerprint']) == len(intent['request_fingerprint']) == 64
        assert intent['model'] == kwargs['json']['model'] == 'auto'
        # Opening a writer proves no SQLite transaction encloses network I/O.
        with sqlite3.connect(fixture.DB, timeout=0) as db:
            db.execute('BEGIN IMMEDIATE')
            db.rollback()
    http.before_network = intent_check
    first = runtime.execute_authorized_claimed_ai_runtime(pid, provider=p)
    assert first['production_result']['status'] == 'submitted'
    assert first['runtime_job']['status'] == first['production_task'].status == 'running'
    assert http.posts == 1
    request_id = http.sent['headers']['Idempotency-Key']
    second = runtime.execute_authorized_claimed_ai_runtime(pid, provider=p)
    assert second['production_result']['id'] == first['production_result']['id'] and http.posts == 1
    print('G4C_DURABLE_INTENT_BEFORE_POST=PASS')
    print('G4C_REQUEST_ID_SERVER_OWNED=PASS')
    print('G4C_REQUEST_ID_STABLE=PASS')
    print('G4C_REQUEST_FINGERPRINT=PASS')
    print('G4C_ENDPOINT_FINGERPRINT=PASS')
    print('G4C_MODEL_SERVER_OWNED=PASS')
    print('G4C_ENDPOINT_SERVER_OWNED=PASS')
    print('G4C_FIRST_EXECUTOR_POSTS_ONCE=PASS')
    print('G4C_SECOND_EXECUTOR_NO_POST=PASS')
    http.get_data = {'status': 'running'}
    active = runtime.refresh_authorized_ai_runtime(pid, provider=p)
    assert active['production_result']['status'] == 'running' and http.posts == 1
    import requests
    http.get_data = requests.Timeout(SECRET)
    transient = runtime.refresh_authorized_ai_runtime(pid, provider=p)
    assert transient['production_result']['status'] == 'running' and http.posts == 1
    print('G4C_TEMP_POLL_FAILURE_STAYS_RUNNING=PASS')
    http.get_data = {'status': 'completed', 'asset_url': ASSET}
    barrier = threading.Barrier(4)
    def poll(_):
        barrier.wait()
        return runtime.refresh_authorized_ai_runtime(pid, provider=p)
    with ThreadPoolExecutor(max_workers=4) as pool:
        done = list(pool.map(poll, range(4)))
    assert len({r['production_result']['id'] for r in done}) == 1
    assert all(r['production_result']['status'] == r['runtime_job']['status'] == r['production_task'].status == 'completed' for r in done)
    assert http.posts == 1
    print('G4C_POLL_CONCURRENCY=PASS')
    for _ in range(3):
        for function in (runtime.execute_authorized_claimed_ai_runtime, runtime.refresh_authorized_ai_runtime):
            result = function(pid, provider=p)['production_result']
            assert result['id'] == first['production_result']['id']
            assert result['output']['job_id'] == 'remote-1' and result['output']['asset_url'] == ASSET
    assert http.posts == 1 and http.sent['headers']['Idempotency-Key'] == request_id
    assert fixture._counts() == {'production_tasks': 1, 'runtime_jobs': 1, 'production_results': 1, 'video_assets': 0, 'publish_tasks': 0}
    print('G4C_CANONICAL_HAPPY_PATH=PASS')
    print('G4C_RUNTIME_JOB_COUNT=1')
    print('G4C_PRODUCTION_RESULT_COUNT=1')
    print('G4C_NO_VIDEO_ASSET=PASS')
    print('G4C_NO_PUBLISH_TASK=PASS')
    print('G4C_TERMINAL_REPLAY_IDEMPOTENT=PASS')
    from production.results.manager import update_result
    sealed = update_result(result['id'], status='completed', output=result['output'])
    assert sealed['status'] == 'completed' and not sealed.get('asset_id')
    assert fixture._counts()['video_assets'] == 0
    print('G4C_GENERIC_ASSET_DEFERRAL=PASS')

    for round_no in range(20):
        cp, cj = claimed('race-' + str(round_no))
        rp, rh = provider()
        barrier = threading.Barrier(4)
        def execute(_):
            barrier.wait()
            try:
                return runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp)
            except ValueError as exc:
                assert 'claimed' in str(exc)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(execute, range(4)))
        assert rh.posts == 1
        assert len([r for r in get_results() if r['runtime_job_id'] == cj]) == 1
        with sqlite3.connect(fixture.DB) as db:
            assert db.execute('SELECT COUNT(*) FROM runtime_jobs WHERE task_id=?', (get_job(cj)['task_id'],)).fetchone()[0] == 1
            assert db.execute('SELECT COUNT(*) FROM production_tasks WHERE idempotency_key=?', (f'content-plan:{cp}:revision:1',)).fetchone()[0] == 1
    print('G4C_CONCURRENCY_ROUNDS=20')
    print('G4C_CONCURRENT_POST_AT_MOST_ONCE=PASS')

    for label in ('kill', 'off', 'override', 'revision'):
        cp, cj = claimed('auth-' + label, review=label == 'override')
        rp, rh = provider()
        def mutate():
            if label == 'kill':
                autonomy.update_autonomy_settings(kill_switch_active=True)
            elif label == 'off':
                autonomy.update_autonomy_settings(autonomy_enabled=False)
            elif label == 'override':
                autonomy.clear_policy_override(cp, 'isolated revocation')
            else:
                with sqlite3.connect(fixture.DB) as db:
                    db.execute('UPDATE intelligence_content_plans SET revision=revision+1 WHERE id=?', (cp,))
        rejected(lambda: runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp, before_post=mutate))
        assert rh.posts == 0 and get_job(cj)['execution_state'] == 'dispatch_intent'
        print({'kill': 'G4C_KILL_SWITCH_BEFORE_POST=PASS', 'off': 'G4C_AUTONOMY_OFF_BEFORE_POST=PASS',
               'override': 'G4C_OVERRIDE_REVOKE_BEFORE_POST=PASS', 'revision': 'G4C_STALE_REVISION_BEFORE_POST=PASS'}[label])
    print('G4C_FRESH_AUTH_BEFORE_POST=PASS')

    cp, cj = claimed('route')
    rp, rh = provider()
    os.environ['OS_PRODUCTION_PROVIDER'] = 'github'
    runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp)
    assert rh.posts == 1 and get_job(cj)['provider'] == 'ai_gateway'
    print('G4C_PERSISTED_ROUTE_WINS=PASS')
    rp.gateway.providers['video'].endpoint_override = 'https://other.example.test/video'
    rejected(lambda: runtime.refresh_authorized_ai_runtime(cp, provider=rp))
    assert rh.gets == 0 and rh.posts == 1
    print('G4C_ENDPOINT_DRIFT_FAIL_CLOSED=PASS')
    rp.gateway.providers['video'].endpoint_override = ENDPOINT
    with sqlite3.connect(fixture.DB) as db:
        raw = json.loads(get_job(cj)['input'])
        raw['parameters']['prompt'] = 'altered'
        db.execute('UPDATE runtime_jobs SET input=? WHERE id=?', (json.dumps(raw), cj))
    rejected(lambda: runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp))
    assert rh.posts == 1
    print('G4C_REQUEST_DRIFT_FAIL_CLOSED=PASS')

    cp, cj = claimed('precrash')
    rp, rh = provider()
    def crash():
        raise RuntimeError('simulated process loss')
    rejected(lambda: runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp, before_post=crash))
    rejected(lambda: runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp))
    rejected(lambda: runtime.refresh_authorized_ai_runtime(cp, provider=rp))
    assert rh.posts == 0
    print('G4C_PRE_POST_CRASH_NO_REDISPATCH=PASS')
    cp, cj = claimed('postcrash')
    rp, rh = provider()
    rh.post_data = requests.Timeout(SECRET)
    rejected(lambda: runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp))
    rejected(lambda: runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp))
    assert rh.posts == 1 and get_job(cj)['execution_state'] == 'ambiguous_dispatch'
    print('G4C_POST_AMBIGUOUS_NO_REDISPATCH=PASS')
    cp, cj = claimed('persistcrash')
    rp, rh = provider()
    with patch.object(runtime, 'create_or_get_result_for_job', side_effect=RuntimeError('disk failure')):
        rejected(lambda: runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp))
    recovered = runtime.refresh_authorized_ai_runtime(cp, provider=rp)
    assert recovered['production_result']['status'] == 'completed' and rh.posts == 1
    print('G4C_CORRELATION_PERSISTENCE_RECOVERY=PASS')

    # Response arrives but even correlation persistence fails: retry is still
    # blocked by the earlier durable intent, without trusting in-memory output.
    cp, cj = claimed('correlation-write-failure')
    rp, rh = provider()
    with patch.object(runtime, 'update_execution_metadata', side_effect=RuntimeError('disk unavailable')):
        rejected(lambda: runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp))
    rejected(lambda: runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp))
    assert rh.posts == 1
    print('G4C_POST_PERSISTENCE_FAILURE_NO_REDISPATCH=PASS')

    cp, cj = claimed('unconfigured')
    rp, rh = provider(endpoint='')
    before = get_job(cj)
    rejected(lambda: runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp))
    assert get_job(cj) == before and rh.posts == 0
    rp, rh = provider()
    os.environ.pop('OS_AI_VIDEO_AUTONOMOUS_EXECUTION_ENABLED')
    rejected(lambda: runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp))
    assert get_job(cj) == before and rh.posts == 0
    os.environ['OS_AI_VIDEO_AUTONOMOUS_EXECUTION_ENABLED'] = 'true'
    print('G4C_UNCONFIGURED_NO_MUTATION=PASS')
    print('G4C_DEFAULT_OFF_EXECUTION_SWITCH=PASS')

    # Real canonical synchronous terminal responses synchronize all three rows.
    for terminal in ('completed', 'failed'):
        cp, cj = claimed('terminal-' + terminal)
        rp, rh = provider()
        rh.post_data = {'status': terminal, 'asset_url': ASSET, 'error': SECRET if terminal == 'failed' else ''}
        terminal_row = runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp)
        assert terminal_row['production_result']['status'] == terminal_row['runtime_job']['status'] == terminal_row['production_task'].status == terminal
        assert rh.posts == 1 and not terminal_row['production_result'].get('asset_id')
    print('G4C_TERMINAL_STATUS_SYNC=PASS')

    # A legacy worker must not bypass the canonical autonomous entrypoint.
    from production.runtime.worker import ProductionRuntimeWorker
    rejected(lambda: ProductionRuntimeWorker().run(get_job(cj)))
    assert rh.posts == 1
    print('G4C_LEGACY_WORKER_NO_AUTH_BYPASS=PASS')
    cp, cj = claimed('stale-worker-poll')
    rp, rh = provider()
    stale_job = get_job(cj)
    runtime.execute_authorized_claimed_ai_runtime(cp, provider=rp)
    autonomy.update_autonomy_settings(kill_switch_active=True)
    rejected(lambda: ProductionRuntimeWorker().poll(stale_job, provider_override=rp))
    assert rh.gets == 0 and rh.posts == 1
    fixture._enable()
    print('G4C_STALE_WORKER_POLL_AUTH_GUARD=PASS')

    transport = provider()[0].gateway.providers['video']
    for data in ([], {'status': 'nonsense'}, {'status': 'running'}, {'status': 'completed'},
                 {'status': 'failed', 'error': SECRET}):
        r = transport._normalize_payload(data)
        assert r.status == 'failed' and SECRET not in str(r)
    assert transport._normalize_payload({'status': 'completed', 'video_url': ASSET}).output['asset_url'] == ASSET
    active_secret = transport._normalize_payload({'status': 'running', 'poll_url': '/jobs/1',
                                                  'asset_url': SECRET, 'headers': {'Authorization': SECRET},
                                                  'model': SECRET, 'usage': {'key': SECRET}})
    assert active_secret.status == 'running' and SECRET not in str(active_secret)
    print('G4C_ACTIVE_REQUIRES_POLL_URL=PASS')
    print('G4C_COMPLETED_REMOTE_ASSET_REFERENCE=PASS')
    assert transport._poll_url({'poll_url': '/jobs/1'}) == 'https://gateway.example.test:443/jobs/1'
    assert transport._poll_url({'poll_url': 'https://gateway.example.test/jobs/1'}) == 'https://gateway.example.test/jobs/1'
    print('G4C_POLL_URL_SAME_ORIGIN=PASS')
    for url in ('https://evil.invalid/x', 'http://127.0.0.1/x', 'http://[::1]/', 'https://169.254.169.254/',
                '//evil.invalid/x', 'https://gateway.example.test:444/x', 'https://u:p@gateway.example.test/x'):
        rejected(lambda: transport._poll_url({'poll_url': url}))
    print('G4C_POLL_URL_CROSS_ORIGIN_BLOCKED=PASS')
    for url in ('file:///x', 'data:x', 'javascript:x', 'https://localhost/x', 'https://10.0.0.1/x', 'https://127.0.0.1/x'):
        rejected(lambda: transport._asset_url(url))
    with patch.object(Response, 'status_code', 302):
        assert transport.poll({'status_url': '/jobs/1'}).status == 'failed'
    print('G4C_POLL_REDIRECT_FAIL_CLOSED=PASS')
    for data in (ValueError(SECRET), []):
        transport.session.post_data = data
        assert transport.request(AIRequest('video_generation')).status == 'failed'
    with patch.object(Response, 'status_code', 500):
        assert transport.request(AIRequest('video_generation')).status == 'failed'
    print('G4C_PROVIDER_RESPONSE_VALIDATION=PASS')
    with sqlite3.connect(fixture.DB) as db:
        serialized = '\n'.join(db.iterdump())
    assert SECRET not in serialized
    assert fixture._counts()['video_assets'] == fixture._counts()['publish_tasks'] == 0
    print('G4C_SECRET_PERSISTENCE=0')
    print('REAL_AI_GATEWAY_POST_COUNT=0')
    print('REAL_AI_GATEWAY_GET_COUNT=0')
    print('G4C_AI_PRODUCTION_LINE_SMOKE=PASS')


if __name__ == '__main__':
    try:
        captured = io.StringIO()
        with redirect_stdout(captured), redirect_stderr(captured):
            with patch.object(socket.socket, 'connect', blocked), patch.object(socket, 'create_connection', blocked):
                main()
        assert SECRET not in captured.getvalue()
        print(captured.getvalue(), end='')
        print('G4C_SECRET_LOG_LEAK=0')
    finally:
        gc.collect()
        fixture.DB.unlink(missing_ok=True)
