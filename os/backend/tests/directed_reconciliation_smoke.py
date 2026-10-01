"""Isolated, network-free directed unknown intent recovery contract."""
from test_database_helper import TEST_DATABASE_PATH

import json
import socket
import sqlite3
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.directed_operator import ALLOWLIST_ENV, authorize_directed_reconciliation
from intelligence.content_brain import ContentPlan, directed_creation_identity, save_plan
from intelligence.feedback_bridge import record_directed_generation_intent, get_directed_request_status
from intelligence import directed_reconciliation as recovery
from admin import reconcile_directed_request as admin_cli
from routers.intelligence import ContentPlanGenerationRequest
import routers.intelligence as route
from fastapi import HTTPException
from pydantic import ValidationError


def denied(fn, code):
    try:
        fn()
    except (ValueError, PermissionError) as exc:
        assert code in str(exc), (code, exc)
    else:
        raise AssertionError('expected ' + code)


def main():
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        sid = 'S-1-5-21-101-202-303-404'
        fake = lambda: sid
        denied(lambda: authorize_directed_reconciliation(sid_provider=fake, environ={}, platform_name='win32'), 'ALLOWLIST')
        denied(lambda: authorize_directed_reconciliation(sid_provider=fake, environ={ALLOWLIST_ENV: ''}, platform_name='win32'), 'ALLOWLIST')
        denied(lambda: authorize_directed_reconciliation(sid_provider=fake, environ={ALLOWLIST_ENV: 'bad'}, platform_name='win32'), 'ALLOWLIST')
        denied(lambda: authorize_directed_reconciliation(sid_provider=lambda: None, environ={ALLOWLIST_ENV: sid}, platform_name='win32'), 'PROCESS_SID')
        denied(lambda: authorize_directed_reconciliation(sid_provider=fake, environ={ALLOWLIST_ENV: 'S-1-5-21-1-2-3-5'}, platform_name='win32'), 'NOT_ALLOWED')
        denied(lambda: authorize_directed_reconciliation(sid_provider=fake, environ={ALLOWLIST_ENV: sid}, platform_name='linux'), 'WINDOWS_ONLY')
        actor = authorize_directed_reconciliation(sid_provider=fake, environ={ALLOWLIST_ENV: sid}, platform_name='win32')
        assert actor == authorize_directed_reconciliation(sid_provider=fake, environ={ALLOWLIST_ENV: sid}, platform_name='win32')
        assert actor.startswith('windows-sid-sha256:') and sid not in actor
        try:
            ContentPlanGenerationRequest(request_id=uuid.uuid4(), human_brief='Safe brief', actor_id='admin')
        except ValidationError:
            pass
        else:
            raise AssertionError('client actor accepted')
        print('OPERATOR_AUTH=PASS')

        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            conn.execute('CREATE TABLE intelligence_feedback_snapshots(id INTEGER PRIMARY KEY, directed_requests_json TEXT)')
            conn.execute('CREATE TABLE intelligence_content_plans(id INTEGER PRIMARY KEY, plan_key TEXT UNIQUE, source_snapshot_id INTEGER, content_id TEXT, status TEXT, revision INTEGER DEFAULT 1, approved_revision INTEGER, payload_json TEXT, created_at TEXT, updated_at TEXT)')
            conn.execute('INSERT INTO intelligence_feedback_snapshots VALUES(11, ?)', ('{}',))

        tokens = [str(uuid.uuid4()) for _ in range(8)]
        ids = [directed_creation_identity(token, 11, 'Brief', {})[0] for token in tokens]
        legacy = {ids[0]: {'fingerprint': 'f0', 'created_at': '2026-01-01T00:00:00+00:00'}}
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            conn.execute('UPDATE intelligence_feedback_snapshots SET directed_requests_json=? WHERE id=11', (json.dumps(legacy),))
        assert get_directed_request_status(11, ids[0])['effective_state'] == 'UNRESOLVED_UNKNOWN'
        denied(lambda: record_directed_generation_intent(11, ids[0], 'f0'), 'PENDING_OR_UNKNOWN')
        denied(lambda: record_directed_generation_intent(11, ids[1], 'f1'), 'RECONCILIATION_REQUIRED')
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            assert json.loads(conn.execute('SELECT directed_requests_json FROM intelligence_feedback_snapshots WHERE id=11').fetchone()[0]) == legacy
            conn.execute('INSERT INTO intelligence_content_plans(plan_key,payload_json) VALUES(?,?)', ('directed-request:' + ids[0], '{}'))
        assert get_directed_request_status(11, ids[0])['effective_state'] == 'COMPLETED'
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            data=json.loads(conn.execute('SELECT directed_requests_json FROM intelligence_feedback_snapshots WHERE id=11').fetchone()[0])
            data[ids[0]]['state']='CONFIRMED_FAILED'
            conn.execute('UPDATE intelligence_feedback_snapshots SET directed_requests_json=? WHERE id=11', (json.dumps(data),))
        conflicted=get_directed_request_status(11, ids[0])
        assert conflicted['effective_state']=='COMPLETED' and conflicted['state_conflict']
        exposed=route.directed_request_status(11, uuid.UUID(tokens[0]))
        assert set(exposed)=={'request_id','effective_state','can_create_new_request','requires_duplicate_risk_ack'}
        assert exposed['effective_state']=='COMPLETED' and not exposed['can_create_new_request']
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            data[ids[0]].pop('state')
            conn.execute('UPDATE intelligence_feedback_snapshots SET directed_requests_json=? WHERE id=11', (json.dumps(data),))
        print('EFFECTIVE_STATE=PASS')

        with patch.object(recovery, 'authorize_directed_reconciliation', return_value=actor):
            denied(lambda: recovery.reconcile_directed_request(11, tokens[0], expected_state='UNRESOLVED_UNKNOWN', target_state='CONFIRMED_FAILED', reason_code='PROVIDER_CONFIRMED_NO_RESULT', evidence_reference='provider:proof-1'), 'CANONICAL_PLAN_ALREADY_EXISTS')
            record_directed_generation_intent(11, ids[1], 'f1')
            denied(lambda: recovery.reconcile_directed_request(11, tokens[1], expected_state='UNRESOLVED_UNKNOWN', target_state='COMPLETED', reason_code='PROVIDER_CONFIRMED_NO_RESULT', evidence_reference='provider:proof-1'), 'TARGET_STATE_INVALID')
            denied(lambda: recovery.reconcile_directed_request(11, tokens[1], expected_state='UNRESOLVED_UNKNOWN', target_state='CONFIRMED_FAILED', reason_code='HTTP_502', evidence_reference='provider:proof-1'), 'REASON_CODE_INVALID')
            denied(lambda: recovery.reconcile_directed_request(11, tokens[1], expected_state='UNRESOLVED_UNKNOWN', target_state='CONFIRMED_FAILED', reason_code='PROVIDER_CONFIRMED_NO_RESULT', evidence_reference=''), 'EVIDENCE_REFERENCE_INVALID')
            failed = recovery.reconcile_directed_request(11, tokens[1], expected_state='UNRESOLVED_UNKNOWN', target_state='CONFIRMED_FAILED', reason_code='PROVIDER_CONFIRMED_NO_RESULT', evidence_reference='provider:proof-1')
            assert failed['effective_state'] == 'CONFIRMED_FAILED' and not failed['replayed']
            with sqlite3.connect(TEST_DATABASE_PATH) as conn:
                record=json.loads(conn.execute('SELECT directed_requests_json FROM intelligence_feedback_snapshots WHERE id=11').fetchone()[0])[ids[1]]
            assert record['reconciliation']['actor_id']==actor and sid not in json.dumps(record)
            assert set(record['reconciliation'])=={'at','actor_id','reason_code','evidence_reference'}
            assert recovery.reconcile_directed_request(11, tokens[1], expected_state='UNRESOLVED_UNKNOWN', target_state='CONFIRMED_FAILED', reason_code='PROVIDER_CONFIRMED_NO_RESULT', evidence_reference='provider:proof-1')['replayed']
            denied(lambda: recovery.reconcile_directed_request(11, tokens[1], expected_state='UNRESOLVED_UNKNOWN', target_state='CONFIRMED_FAILED', reason_code='PROVIDER_CONFIRMED_NO_RESULT', evidence_reference='provider:other'), 'STATE_CONFLICT')
            denied(lambda: recovery.reconcile_directed_request(11, tokens[1], expected_state='UNRESOLVED_UNKNOWN', target_state='CLOSED_UNKNOWN', reason_code='OUTCOME_EVIDENCE_UNAVAILABLE', evidence_reference='audit:bounded-1', duplicate_risk_ack=True), 'STATE_CONFLICT')
            record_directed_generation_intent(11, ids[2], 'f2')
            denied(lambda: recovery.reconcile_directed_request(11, tokens[2], expected_state='UNRESOLVED_UNKNOWN', target_state='CLOSED_UNKNOWN', reason_code='OUTCOME_EVIDENCE_UNAVAILABLE', evidence_reference='audit:bounded-1'), 'RISK_ACK_REQUIRED')
            recovery.reconcile_directed_request(11, tokens[2], expected_state='UNRESOLVED_UNKNOWN', target_state='CLOSED_UNKNOWN', reason_code='OUTCOME_EVIDENCE_UNAVAILABLE', evidence_reference='audit:bounded-1', duplicate_risk_ack=True)
            denied(lambda: record_directed_generation_intent(11, ids[3], 'f3'), 'RISK_ACK_REQUIRED')
            record_directed_generation_intent(11, ids[3], 'f3', duplicate_risk_ack=True)
            assert get_directed_request_status(11, ids[3])['effective_state'] == 'UNRESOLVED_UNKNOWN'
            plan = ContentPlan(content_id=ids[3], topic='Verify a payment', angle='Receiving side',
                target_audience='Freelancers', hook='Check the balance.', script='Confirm the credited deposit.',
                cta='Read the guide.', title='Payment check', description='Payment education',
                generation_evidence={'request_fingerprint': 'f3'})
            def finish(kind):
                try:
                    if kind == 'plan':
                        save_plan(plan, 11, directed_request=True)
                    else:
                        recovery.reconcile_directed_request(11, tokens[3], expected_state='UNRESOLVED_UNKNOWN',
                            target_state='CONFIRMED_FAILED', reason_code='PROVIDER_CONFIRMED_NO_RESULT',
                            evidence_reference='provider:race-proof')
                    return kind
                except ValueError as exc:
                    assert 'DIRECTED_' in str(exc)
                    return 'blocked'
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(finish, ('plan', 'reconcile')))
            assert outcomes.count('blocked') == 1 and get_directed_request_status(11, ids[3])['effective_state'] in ('COMPLETED', 'CONFIRMED_FAILED')
            record_directed_generation_intent(11, ids[4], 'f4', duplicate_risk_ack=True)
            def terminal(kind):
                try:
                    recovery.reconcile_directed_request(11, tokens[4], expected_state='UNRESOLVED_UNKNOWN',
                        target_state=kind, reason_code='PROVIDER_CONFIRMED_NO_RESULT' if kind == 'CONFIRMED_FAILED' else 'OUTCOME_EVIDENCE_UNAVAILABLE',
                        evidence_reference='provider:terminal-race' if kind == 'CONFIRMED_FAILED' else 'audit:terminal-race',
                        duplicate_risk_ack=kind == 'CLOSED_UNKNOWN')
                    return 'won'
                except ValueError as exc:
                    assert 'STATE_CONFLICT' in str(exc)
                    return 'blocked'
            with ThreadPoolExecutor(max_workers=2) as pool:
                assert sorted(pool.map(terminal, ('CONFIRMED_FAILED', 'CLOSED_UNKNOWN'))) == ['blocked', 'won']
            record_directed_generation_intent(11, ids[5], 'f5', duplicate_risk_ack=True)
            cli_args = ['11', tokens[5], 'CLOSED_UNKNOWN', 'OUTCOME_EVIDENCE_UNAVAILABLE', 'audit:cli-proof', '--duplicate-risk-ack']
            with patch.object(admin_cli, 'authorize_directed_reconciliation', return_value=actor):
                assert admin_cli.main(cli_args, confirm=lambda _: '') == 1
                assert get_directed_request_status(11, ids[5])['effective_state'] == 'UNRESOLVED_UNKNOWN'
                assert admin_cli.main(cli_args, confirm=lambda _: 'RECONCILE') == 0
                assert get_directed_request_status(11, ids[5])['effective_state'] == 'CLOSED_UNKNOWN'
            print('LOCAL_ADMIN_CLI_CONFIRMATION=PASS')
            class FakeProvider:
                supports_directed=True
                calls=0
                def readiness(self): return {'runtime_ready': True}
                def generate_content_plan(self, snapshot, context):
                    self.calls += 1
                    return ContentPlan(content_id='model-injected', topic='Verify a payment', angle='Receiving side',
                        target_audience='Freelancers', hook='Check the balance.', script='Confirm the credited deposit.',
                        cta='Read the guide.', title='Payment check', description='Payment education')
            fake=FakeProvider()
            snapshot={'id':11, 'content_id':'source', 'metrics_snapshot':{'learning_evidence':{'fingerprint':'fixture', 'window':['2026-01-01','2026-01-31']}}}
            new_uuid=uuid.uuid4()
            with patch.object(route, 'get_feedback_snapshot', return_value=snapshot), patch.object(route, 'select_content_plan_provider', return_value=fake), patch.object(route, '_plan_with_policy', side_effect=lambda saved, runtime: {'plan':saved}):
                try: route.generate_content_plan(11, ContentPlanGenerationRequest(request_id=new_uuid, human_brief='Verify the deposit.'))
                except HTTPException as exc: assert exc.status_code==409 and exc.detail=='DIRECTED_DUPLICATE_RISK_ACK_REQUIRED'
                else: raise AssertionError('risk acknowledgement gate missing')
                assert fake.calls==0
                result=route.generate_content_plan(11, ContentPlanGenerationRequest(request_id=new_uuid, human_brief='Verify the deposit.', duplicate_risk_ack=True))
                assert fake.calls==1 and result['plan']['plan']['content_id']==directed_creation_identity(new_uuid,11,'Verify the deposit.',{})[0]
                route.generate_content_plan(11, ContentPlanGenerationRequest(request_id=new_uuid, human_brief='Verify the deposit.'))
                assert fake.calls==1
            print('CLOSED_UNKNOWN_ROUTE_ACK_NO_PREMATURE_PROVIDER_CALL=PASS')
            print('RECONCILIATION=PASS')
            print('EVIDENCE=PASS')
            print('SAME_SNAPSHOT_GATE=PASS')

            def race(i):
                try:
                    record_directed_generation_intent(12, ids[6+i], 'race'+str(i))
                    return 'claimed'
                except ValueError as exc:
                    assert 'RECONCILIATION_REQUIRED' in str(exc)
                    return 'blocked'
            with sqlite3.connect(TEST_DATABASE_PATH) as conn:
                conn.execute('INSERT INTO intelligence_feedback_snapshots VALUES(12, ?)', ('{}',))
            with ThreadPoolExecutor(max_workers=2) as pool:
                assert sorted(pool.map(race, range(2))) == ['blocked', 'claimed']
            print('CONCURRENCY=PASS')
        print('NETWORK_TRIPWIRE=PASS')


if __name__ == '__main__':
    main()
