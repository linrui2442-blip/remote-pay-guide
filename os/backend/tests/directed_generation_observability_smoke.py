"""Offline forensic metadata contract for one-shot directed generation."""
from test_database_helper import TEST_DATABASE_PATH

import json
import socket
import sqlite3
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from intelligence.content_brain import LLMContentPlanProvider, directed_creation_identity
from intelligence.feedback_bridge import (_ensure_table, get_directed_request_status,
    record_directed_generation_intent, record_directed_generation_observation)
import routers.intelligence as route


GOOD = dict(topic='Verify a payment deposit', angle='Receiving-side confirmation',
    target_audience='Freelancers', hook='Check your receiving balance.',
    script='Open deposit history and confirm the payment is credited.',
    cta='Read Remote Pay Guide.', title='Confirm payment receipt',
    description='Payment education', production_notes='Practical steps',
    visual_direction='Receipt review', reasoning_summary='Verify at the receiving platform',
    strategy_type='iterate', hashtags=['#Freelancer'])


class FakeText:
    model = 'offline'
    def __init__(self, output):
        self.output = output
        self.calls = 0
    def readiness(self):
        return {'runtime_ready': True}
    def request(self, request):
        self.calls += 1
        return {'output': self.output}


def snapshot(number):
    _ensure_table()
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        cursor = conn.execute('''INSERT INTO intelligence_feedback_snapshots
            (account_id, platform, content_id, snapshot_key, feedback_json, strategy_json,
             metrics_json, funnel_json, created_at)
            VALUES (1, 'youtube', ?, ?, '{}', '{}', ?, '{}', '2026-10-03T00:00:00+00:00')''',
            (f'offline-{number}', f'offline-{number}',
             json.dumps({'learning_evidence': {'fingerprint': 'offline-proof',
                                               'window': ['2026-09-01', '2026-09-20']}})))
        return cursor.lastrowid


def observation(sid, identity):
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        raw = conn.execute('SELECT directed_requests_json FROM intelligence_feedback_snapshots WHERE id=?',
                           (sid,)).fetchone()[0]
    return json.loads(raw)[identity], raw


def main():
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        cases = [
            ('PARSE_FAILURE', 'not JSON SECRET_SENTINEL_MODEL_OUTPUT', {},
             'DIRECTED_GENERATION_PARSE_ERROR', 'CONTENT_EXTRACTED'),
            ('SCHEMA_FAILURE', json.dumps({'topic': 'Incomplete'}), {},
             'DIRECTED_GENERATION_SCHEMA_ERROR', 'JSON_PARSED'),
            ('GENERATED_SAFETY_FAILURE', json.dumps({**GOOD, 'script': 'Ask for their private key.'}), {},
             'DIRECTED_GENERATION_SAFETY_REJECTED', 'SCHEMA_VALIDATED'),
            ('MUST_INCLUDE_FAILURE', json.dumps(GOOD), {'must_include': ['invoice number']},
             'DIRECTED_GENERATION_MUST_INCLUDE_REJECTED', 'SAFETY_VALIDATED'),
            ('MUST_AVOID_FAILURE', json.dumps(GOOD), {'must_avoid': ['credited']},
             'DIRECTED_GENERATION_MUST_AVOID_REJECTED', 'SAFETY_VALIDATED'),
            ('FINAL_VALIDATION_FAILURE', json.dumps({**GOOD, 'visual_direction': 'Show a private key'}), {},
             'DIRECTED_GENERATION_CONTENT_PLAN_VALIDATION_ERROR', 'CONSTRAINTS_VALIDATED'),
        ]
        for number, (marker, output, constraints, code, stage) in enumerate(cases):
            sid = snapshot(number)
            token = uuid.uuid4()
            identity, _ = directed_creation_identity(token, sid, 'Safe payment education', constraints)
            fake = FakeText(output)
            request = route.ContentPlanGenerationRequest(request_id=token,
                human_brief='Safe payment education', human_constraints=constraints)
            with patch.object(route, 'select_content_plan_provider', return_value=LLMContentPlanProvider(fake)):
                try:
                    route.generate_content_plan(sid, request)
                except HTTPException as exc:
                    assert exc.status_code == 422 and exc.detail == {'code': code, 'stage': stage}, exc.detail
                else:
                    raise AssertionError('expected 422')
                assert fake.calls == 1
                try:
                    route.generate_content_plan(sid, request)
                except HTTPException as exc:
                    assert exc.status_code == 409
                else:
                    raise AssertionError('same token retried')
                assert fake.calls == 1
            record, raw = observation(sid, identity)
            assert record['state'] == 'UNRESOLVED_UNKNOWN'
            assert get_directed_request_status(sid, identity)['effective_state'] == 'UNRESOLVED_UNKNOWN'
            evidence = record['generation_observation']
            assert evidence['provider_returned_at'] and evidence['last_stage'] == stage
            assert evidence['failure_code'] == code and evidence['failure_at']
            if marker == 'MUST_INCLUDE_FAILURE':
                assert evidence['failed_requirement_index'] == 0
            else:
                assert 'failed_requirement_index' not in evidence
            for secret in ('SECRET_SENTINEL_API_KEY', 'SECRET_SENTINEL_PROMPT',
                           'SECRET_SENTINEL_MODEL_OUTPUT', 'SECRET_SENTINEL_HEADER'):
                assert secret not in raw
            with sqlite3.connect(TEST_DATABASE_PATH) as conn:
                assert conn.execute('SELECT COUNT(*) FROM intelligence_content_plans').fetchone()[0] == 0
                names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                assert 'intelligence_policy_decisions' not in names or conn.execute(
                    'SELECT COUNT(*) FROM intelligence_policy_decisions').fetchone()[0] == 0
            print(marker + '=PASS')

        sid = snapshot('success')
        token = uuid.uuid4()
        identity, _ = directed_creation_identity(token, sid, 'Safe payment education', {})
        fake = FakeText(json.dumps(GOOD))
        request = route.ContentPlanGenerationRequest(request_id=token, human_brief='Safe payment education')
        with patch.object(route, 'select_content_plan_provider', return_value=LLMContentPlanProvider(fake)):
            result = route.generate_content_plan(sid, request)
            assert result['plan']['plan']['content_id'] == identity
            assert route.generate_content_plan(sid, request)['plan']['id'] == result['plan']['id']
            assert fake.calls == 1
        record, raw = observation(sid, identity)
        assert record['generation_observation']['last_stage'] == 'CONTENT_PLAN_PERSISTED'
        assert record['generation_observation']['failure_code'] is None
        assert 'failed_requirement_index' not in record['generation_observation']
        assert record['generation_observation']['provider_returned_at']
        assert get_directed_request_status(sid, identity)['effective_state'] == 'COMPLETED'
        print('SUCCESS_PATH=PASS')

        sid = snapshot('write-failure')
        token = uuid.uuid4()
        fake = FakeText('invalid JSON')
        request = route.ContentPlanGenerationRequest(request_id=token, human_brief='Safe payment education')
        with patch.object(route, 'select_content_plan_provider', return_value=LLMContentPlanProvider(fake)), \
             patch.object(route, 'record_directed_generation_observation', side_effect=RuntimeError('SECRET_SENTINEL_API_KEY')):
            try:
                route.generate_content_plan(sid, request)
            except HTTPException as exc:
                assert exc.status_code == 422 and exc.detail['code'] == 'DIRECTED_GENERATION_PARSE_ERROR'
            else:
                raise AssertionError('primary failure masked')
            assert fake.calls == 1
        print('FAILURE_WRITE_PRIORITY=PASS')

        sid = snapshot('success-write-failure')
        token = uuid.uuid4()
        fake = FakeText(json.dumps(GOOD))
        request = route.ContentPlanGenerationRequest(request_id=token, human_brief='Safe payment education')
        with patch.object(route, 'select_content_plan_provider', return_value=LLMContentPlanProvider(fake)), \
             patch.object(route, 'record_directed_generation_observation', side_effect=RuntimeError('offline write failure')):
            try:
                route.generate_content_plan(sid, request)
            except HTTPException as exc:
                assert exc.status_code == 503 and exc.detail == 'DIRECTED_GENERATION_OBSERVATION_UNAVAILABLE'
            else:
                raise AssertionError('forensic write failure falsely reported success')
            assert fake.calls == 1
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            assert conn.execute('SELECT COUNT(*) FROM intelligence_content_plans WHERE source_snapshot_id=?',
                                (sid,)).fetchone()[0] == 0
        print('SUCCESS_WRITE_FAIL_CLOSED=PASS')

        sid = snapshot('terminal-state')
        token = uuid.uuid4()
        identity, fingerprint = directed_creation_identity(token, sid, 'Safe payment education', {})
        record_directed_generation_intent(sid, identity, fingerprint)
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            raw = conn.execute('SELECT directed_requests_json FROM intelligence_feedback_snapshots WHERE id=?',
                               (sid,)).fetchone()[0]
            intents = json.loads(raw)
            intents[identity]['state'] = 'CONFIRMED_FAILED'
            conn.execute('UPDATE intelligence_feedback_snapshots SET directed_requests_json=? WHERE id=?',
                         (json.dumps(intents), sid))
        try:
            record_directed_generation_observation(sid, identity,
                stage='CONTENT_EXTRACTED', failure_code='DIRECTED_GENERATION_PARSE_ERROR',
                provider_returned=True)
        except ValueError as exc:
            assert str(exc) == 'DIRECTED_RECONCILIATION_STATE_CONFLICT'
        else:
            raise AssertionError('terminal intent observation accepted')
        assert 'generation_observation' not in observation(sid, identity)[0]
        print('TERMINAL_STATE_NOT_REWRITTEN=PASS')

        sid = snapshot('provider-outcome-unknown')
        token = uuid.uuid4()
        identity, _ = directed_creation_identity(token, sid, 'Safe payment education', {})
        fake = FakeText('unused')
        request = route.ContentPlanGenerationRequest(request_id=token, human_brief='Safe payment education')
        with patch.object(route, 'select_content_plan_provider', return_value=LLMContentPlanProvider(fake)), \
             patch.object(fake, 'request', side_effect=ValueError('SECRET_SENTINEL_API_KEY')) as attempted:
            try:
                route.generate_content_plan(sid, request)
            except HTTPException as exc:
                assert exc.status_code == 422
                assert exc.detail == {'code': 'DIRECTED_GENERATION_UNKNOWN_VALIDATION_ERROR',
                                      'stage': 'PROVIDER_OUTCOME_UNCONFIRMED'}
            else:
                raise AssertionError('provider failure accepted')
            assert attempted.call_count == 1
        record, raw = observation(sid, identity)
        assert 'generation_observation' not in record
        assert 'SECRET_SENTINEL_API_KEY' not in raw
        print('UNCONFIRMED_PROVIDER_OUTCOME_NOT_MISLABELLED=PASS')
        print('NO_RETRY=PASS')
        print('NO_RAW_OUTPUT_PERSISTENCE=PASS')
        print('NO_SECRET_PERSISTENCE=PASS')
        print('NETWORK_TRIPWIRE=PASS')


if __name__ == '__main__':
    main()
