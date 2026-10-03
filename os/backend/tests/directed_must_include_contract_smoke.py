"""Offline required-phrase contract and safe item-level observability."""
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
from intelligence.content_brain import (
    LLMContentPlanProvider, _normalize_required_phrase_text, directed_creation_identity,
)
from intelligence.feedback_bridge import _ensure_table
import routers.intelligence as route


REQUIRED = [
    'payment screenshot is not proof of receipt',
    'verify actual wallet/on-chain receipt',
    'payment education',
]
GOOD = dict(topic='Verify a client payment', angle='Receiving-side confirmation',
    target_audience='Freelancers', hook='Check the wallet before closing the invoice.',
    script='A payment screenshot is not proof of receipt. Verify actual wallet/on-chain receipt. This is payment education.',
    cta='Read Remote Pay Guide.', title='Confirm payment receipt',
    description='Check credited funds.', production_notes='Practical steps',
    visual_direction='Receipt review', reasoning_summary='Confirm the actual deposit',
    strategy_type='iterate', hashtags=['#Freelancer'])


class FakeText:
    model = 'offline'
    def __init__(self, data):
        self.data = data
        self.calls = 0
        self.prompt = None
    def readiness(self):
        return {'runtime_ready': True}
    def request(self, request):
        self.calls += 1
        self.prompt = request.prompt
        return {'output': json.dumps(self.data)}


def snapshot():
    _ensure_table()
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        return conn.execute('''INSERT INTO intelligence_feedback_snapshots
            (account_id, platform, content_id, snapshot_key, feedback_json, strategy_json,
             metrics_json, funnel_json, created_at)
            VALUES (1, 'youtube', 'offline-phrase', ?, '{}', '{}', ?, '{}', '2026-10-03T00:00:00+00:00')''',
            (str(uuid.uuid4()), json.dumps({'learning_evidence': {'fingerprint': 'offline-proof',
                                               'window': ['2026-09-01', '2026-09-20']}}))).lastrowid


def record(sid, identity):
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        raw = conn.execute('SELECT directed_requests_json FROM intelligence_feedback_snapshots WHERE id=?',
                           (sid,)).fetchone()[0]
    return json.loads(raw)[identity], raw


def check_normalization():
    match = lambda required, generated: _normalize_required_phrase_text(required) in _normalize_required_phrase_text(generated)
    assert match(REQUIRED[0], REQUIRED[0])
    assert match(REQUIRED[0], REQUIRED[0].upper())
    assert match('  payment screenshot is not proof of receipt  ', REQUIRED[0])
    assert match(REQUIRED[0], 'payment   screenshot is not proof of receipt')
    assert match("don't rely on a payment screenshot", 'Don\u2019t rely on a payment screenshot')
    assert match(REQUIRED[1], 'VERIFY ACTUAL WALLET/ON-CHAIN RECEIPT')
    assert match(REQUIRED[1], 'verify  actual wallet/on-chain\nreceipt')
    assert match(REQUIRED[2], 'PAYMENT EDUCATION')
    assert not match(REQUIRED[0], 'A payment screenshot does not prove you received the funds.')
    assert not match(REQUIRED[1], 'Check your wallet and confirm the transaction on-chain.')
    assert not match(REQUIRED[2], 'Educational guidance for receiving payments')
    assert not match(REQUIRED[1], 'verify actual wallet and on-chain receipt')
    assert not match(REQUIRED[1], 'verify actual wallet/\n on-chain receipt')
    assert not match(REQUIRED[1], 'verify actual wallet/on chain receipt')
    print('EXACT_REQUIRED_PHRASE=PASS')
    print('CASE_VARIATION=PASS')
    print('WHITESPACE_VARIATION=PASS')
    print('TYPOGRAPHIC_QUOTES=PASS')
    print('PARAPHRASE_REJECTED=PASS')
    print('SLASH_AND_HYPHEN_SEMANTICS_PRESERVED=PASS')


def main():
    check_normalization()
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        for invalid in ('payment education', ['  '], [123]):
            sid = snapshot()
            fake = FakeText(GOOD)
            request = route.ContentPlanGenerationRequest(request_id=uuid.uuid4(),
                human_brief='Explain safe receipt verification.',
                human_constraints={'must_include': invalid})
            with patch.object(route, 'select_content_plan_provider', return_value=LLMContentPlanProvider(fake)):
                try:
                    route.generate_content_plan(sid, request)
                except HTTPException as exc:
                    assert exc.status_code == 422
                else:
                    raise AssertionError('invalid required-phrase list accepted')
            assert fake.calls == 0
        print('REQUIRED_PHRASE_LIST_SCHEMA=PASS')
        sid = snapshot()
        token = uuid.uuid4()
        fake = FakeText(GOOD)
        constraints = {'must_include': REQUIRED}
        request = route.ContentPlanGenerationRequest(request_id=token,
            human_brief='Explain safe receipt verification.', human_constraints=constraints)
        with patch.object(route, 'select_content_plan_provider', return_value=LLMContentPlanProvider(fake)):
            result = route.generate_content_plan(sid, request)
        assert result['plan']['plan']['content_id']
        assert fake.calls == 1
        prompt = fake.prompt
        assert 'must_include is a required phrase' in prompt
        assert 'must appear explicitly' in prompt
        assert 'A paraphrase alone does not satisfy a required phrase' in prompt
        assert all(name in prompt for name in ('topic, angle, hook, script, cta, title, or description',
                                               'Obey must-avoid constraints', 'audience and CTA direction'))
        identity, _ = directed_creation_identity(token, sid, 'Explain safe receipt verification.', constraints)
        evidence = record(sid, identity)[0]['generation_observation']
        assert evidence['failure_code'] is None and 'failed_requirement_index' not in evidence
        print('PROMPT_CONTRACT=PASS')
        print('FAKE_PROVIDER_SUCCESS=PASS')
        print('SUCCESS_OBSERVABILITY_CLEAN=PASS')

        sid = snapshot()
        token = uuid.uuid4()
        paraphrases = {**GOOD, 'script': 'A screenshot does not prove funds arrived. Check your wallet and confirm the blockchain transaction. Learn to receive stablecoin payments safely.',
                       'description': 'Guidance for client payment verification.'}
        fake = FakeText(paraphrases)
        request = route.ContentPlanGenerationRequest(request_id=token,
            human_brief='Explain safe receipt verification.', human_constraints=constraints)
        with patch.object(route, 'select_content_plan_provider', return_value=LLMContentPlanProvider(fake)):
            try:
                route.generate_content_plan(sid, request)
            except HTTPException as exc:
                assert exc.status_code == 422 and exc.detail == {
                    'code': 'DIRECTED_GENERATION_MUST_INCLUDE_REJECTED', 'stage': 'SAFETY_VALIDATED'}
            else:
                raise AssertionError('paraphrase accepted')
            try:
                route.generate_content_plan(sid, request)
            except HTTPException as exc:
                assert exc.status_code == 409
            else:
                raise AssertionError('same request retried')
        assert fake.calls == 1
        identity, _ = directed_creation_identity(token, sid, 'Explain safe receipt verification.', constraints)
        evidence = record(sid, identity)[0]['generation_observation']
        assert evidence['failure_code'] == 'DIRECTED_GENERATION_MUST_INCLUDE_REJECTED'
        assert evidence['failed_requirement_index'] == 0
        print('FAKE_PROVIDER_REJECTION=PASS')
        print('MULTIPLE_MISSING_FIRST_INDEX=PASS')
        print('NO_RETRY=PASS')

        sid = snapshot()
        token = uuid.uuid4()
        split_fields = {**GOOD, 'topic': 'payment', 'angle': 'education',
                        'script': 'Verify a client deposit.', 'description': 'Check credited funds.'}
        fake = FakeText(split_fields)
        request = route.ContentPlanGenerationRequest(request_id=token,
            human_brief='Explain safe receipt verification.',
            human_constraints={'must_include': ['payment education']})
        with patch.object(route, 'select_content_plan_provider', return_value=LLMContentPlanProvider(fake)):
            try:
                route.generate_content_plan(sid, request)
            except HTTPException as exc:
                assert exc.status_code == 422 and exc.detail['code'] == 'DIRECTED_GENERATION_MUST_INCLUDE_REJECTED'
            else:
                raise AssertionError('phrase spanning two fields accepted')
        assert fake.calls == 1
        print('CROSS_FIELD_FALSE_POSITIVE_REJECTED=PASS')

        sid = snapshot()
        token = uuid.uuid4()
        sentinel = 'SECRET_MUST_INCLUDE_TEXT_SENTINEL'
        fake = FakeText({**GOOD, 'production_notes': 'SECRET_MODEL_OUTPUT_SENTINEL'})
        special = {'must_include': [REQUIRED[0], sentinel]}
        request = route.ContentPlanGenerationRequest(request_id=token,
            human_brief='Explain safe receipt verification.', human_constraints=special)
        with patch.object(route, 'select_content_plan_provider', return_value=LLMContentPlanProvider(fake)):
            try:
                route.generate_content_plan(sid, request)
            except HTTPException as exc:
                assert exc.status_code == 422
            else:
                raise AssertionError('missing sentinel accepted')
        identity, _ = directed_creation_identity(token, sid, 'Explain safe receipt verification.', special)
        evidence, raw = record(sid, identity)
        assert fake.calls == 1
        assert evidence['generation_observation']['failed_requirement_index'] == 1
        assert sentinel not in raw and 'SECRET_MODEL_OUTPUT_SENTINEL' not in raw
        assert set(evidence['generation_observation']) == {
            'provider_returned_at', 'last_stage', 'failure_code', 'failure_at', 'failed_requirement_index'}
        print('ITEM_LEVEL_OBSERVABILITY=PASS')
        print('NO_RAW_REQUIREMENT_PERSISTENCE=PASS')
        print('NETWORK_TRIPWIRE=PASS')


if __name__ == '__main__':
    main()
