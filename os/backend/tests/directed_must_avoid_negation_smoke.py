"""Network-free must-avoid clause semantics and directed provider contract."""
from test_database_helper import TEST_DATABASE_PATH, assert_safe_test_database_path

import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
assert_safe_test_database_path(TEST_DATABASE_PATH)

from intelligence.content_brain import (
    ContentPlanGenerationError, LLMContentPlanProvider,
    parse_content_plan_response, validate_content_plan,
    validate_generated_content_safety, validate_must_avoid_constraints,
)


def allowed(text, forbidden):
    data = {'script': text}
    assert validate_generated_content_safety(data)
    assert validate_must_avoid_constraints(data, [forbidden])


def denied(text, forbidden):
    try:
        validate_must_avoid_constraints({'script': text}, [forbidden])
    except ContentPlanGenerationError:
        return
    raise AssertionError('positive forbidden occurrence accepted')


def safety_denied(text):
    try:
        validate_generated_content_safety({'script': text})
    except ContentPlanGenerationError:
        return
    raise AssertionError('unsafe positive generated content accepted')


class FakeText:
    model = 'offline'

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def request(self, request):
        self.calls += 1
        assert request.task_type == 'content_plan'
        assert 'Do not positively recommend, promise, instruct, or endorse' in request.prompt
        assert 'A clearly negated safety warning is allowed' in request.prompt
        return {'output': json.dumps(self.payload)}


def main():
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        for marker, text, forbidden in (
            ('NOT_INVESTMENT_ADVICE', 'This is payment education, not investment advice.', 'investment advice'),
            ('DO_NOT_PROVIDE_INVESTMENT_ADVICE', 'Do not provide investment advice.', 'investment advice'),
            ('NO_PROMISES_OF_PROFIT', 'There are no promises of profit.', 'promises of profit'),
            ('NEVER_PROMISE_GUARANTEED_INCOME', 'Never promise guaranteed income.', 'guaranteed income'),
            ('DO_NOT_EVADE_COMPLIANCE', 'Do not give instructions to evade compliance requirements.', 'instructions to evade compliance requirements'),
        ):
            allowed(text, forbidden)
            print(marker + '=PASS')

        for marker, text, forbidden in (
            ('POSITIVE_INVESTMENT_ADVICE', 'This is investment advice.', 'investment advice'),
            ('GUARANTEED_RETURN', 'This token guarantees returns.', 'guarantees returns'),
            ('PROFIT_PROMISE', 'We promise a profit.', 'promise a profit'),
            ('COMPLIANCE_EVASION', 'Here are instructions to evade compliance requirements.', 'instructions to evade compliance requirements'),
        ):
            safety_denied(text)
            denied(text, forbidden)
            print(marker + '=PASS')

        denied('Do not provide investment advice. Here is investment advice: buy token X.', 'investment advice')
        denied('Never promise profit, but this strategy promises profit.', 'promises profit')
        print('CROSS_CLAUSE_UNSAFE_AFTER_NEGATION=PASS')
        denied('Use a casino.', 'casino')
        denied('Do not use a casino.', 'casino')
        print('ARBITRARY_MUST_AVOID_STILL_FAIL_CLOSED=PASS')

        payload = {
            'topic': 'USDT payment education',
            'angle': 'Verify real receipt before treating payment as complete',
            'target_audience': 'freelancers and remote workers receiving international payments',
            'hook': 'A payment screenshot is not proof of receipt.',
            'script': 'A payment screenshot is not proof of receipt. Open the receiving wallet and verify actual wallet/on-chain receipt. This is payment education, not investment advice.',
            'cta': 'Learn safe stablecoin payment receiving with Remote Pay Guide.',
            'title': 'Verify Your USDT Payment Arrived',
            'description': 'Check a credited deposit before treating payment as complete.',
            'production_notes': 'Show a generic receipt without private details.',
            'visual_direction': 'Receipt and receiving-wallet review.',
            'reasoning_summary': 'Receiving-side verification prevents screenshot-only confirmation.',
            'strategy_type': 'directed',
            'hashtags': ['#USDT', '#Freelancer'],
        }
        assert parse_content_plan_response(json.dumps(payload)) == payload
        print('SCHEMA=PASS')
        assert validate_generated_content_safety(payload)
        print('GENERATED_SAFETY=PASS')
        constraints = {
            'target_audience': payload['target_audience'],
            'must_include': ['payment screenshot is not proof of receipt',
                             'verify actual wallet/on-chain receipt', 'payment education'],
            'must_avoid': ['guaranteed income claims', 'investment advice',
                           'promises of profit', 'instructions to evade compliance requirements'],
            'cta_direction': 'educational next step toward learning safe stablecoin payment receiving',
        }
        fake = FakeText(payload)
        plan = LLMContentPlanProvider(fake).generate_content_plan(
            {'id': 11, 'platform': 'youtube'},
            {'human_brief': 'Create educational content for freelancers receiving USDT payments.',
             'human_constraints': constraints, 'content_id': 'directed-' + 'a' * 64})
        assert fake.calls == 1
        assert plan.target_audience == constraints['target_audience']
        print('LOCKED_FIELDS=PASS')
        assert plan.cta == payload['cta']
        print('CTA_DIRECTION=PASS')
        searchable = ' '.join(str(getattr(plan, field)) for field in
                             ('topic', 'angle', 'hook', 'script', 'cta', 'title', 'description')).lower()
        assert all(phrase in searchable for phrase in constraints['must_include'])
        print('MUST_INCLUDE=PASS')
        assert validate_must_avoid_constraints(payload, constraints['must_avoid'])
        assert plan.generation_evidence['constraints_validated']
        print('MUST_AVOID=PASS')
        assert validate_content_plan(plan) is plan
        print('FINAL_CONTENT_PLAN_VALIDATION=PASS')
        print('FULL_DIRECTED_FIXTURE=PASS')


if __name__ == '__main__':
    main()
