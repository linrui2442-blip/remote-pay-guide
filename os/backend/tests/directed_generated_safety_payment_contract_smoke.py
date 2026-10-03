"""Network-free payment-education safety and directed generation contract."""
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
    validate_generated_content_safety, validate_content_plan,
)


def allowed(text):
    assert validate_generated_content_safety({'script': text}) is True


def denied(text):
    try:
        validate_generated_content_safety({'script': text})
    except ContentPlanGenerationError:
        return
    raise AssertionError(f'unsafe content was accepted: {text!r}')


class FakeText:
    model = 'offline'

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def request(self, request):
        self.calls += 1
        assert request.task_type == 'content_plan'
        return {'output': json.dumps(self.payload)}


def main():
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        allowed('USDT payment education explains how to receive a client payment.')
        print('SAFE_USDT_PAYMENT_EDUCATION=PASS')
        allowed('A payment screenshot is not proof of receipt.')
        print('SAFE_SCREENSHOT_NOT_PROOF=PASS')
        allowed('Verify actual wallet/on-chain receipt before closing the invoice.')
        print('SAFE_WALLET_ONCHAIN_VERIFICATION=PASS')
        allowed('This is not investment advice; verify the payment receipt instead.')
        allowed('Do not evade compliance requirements when receiving payment.')
        print('SAFE_NEGATED_WARNINGS=PASS')

        denied('Investment advice: buy this token now.')
        print('INVESTMENT_ADVICE_NEGATIVE=PASS')
        denied('This investment guarantees returns.')
        denied('This payment method guarantees income for freelancers.')
        print('GUARANTEED_RETURN_NEGATIVE=PASS')
        denied('You will definitely make a profit from this.')
        print('PROFIT_PROMISE_NEGATIVE=PASS')
        denied('Follow these instructions to evade compliance requirements.')
        print('COMPLIANCE_EVASION_NEGATIVE=PASS')
        denied('This is not investment advice, but you should buy this token.')
        print('MIXED_WARNING_AND_ADVICE_NEGATIVE=PASS')

        payload = {
            'topic': 'Verify a client USDT payment',
            'angle': 'Confirm receipt before marking the invoice paid',
            'target_audience': 'freelancers and remote workers receiving international payments',
            'hook': 'A payment screenshot is not proof of receipt.',
            'script': 'A payment screenshot is not proof of receipt. Open the wallet you actually receive into and verify actual wallet/on-chain receipt. This is payment education for checking a credited deposit.',
            'cta': 'Learn safe stablecoin payment receiving with Remote Pay Guide.',
            'title': 'Verify Your USDT Payment Arrived',
            'description': 'Check the receiving wallet and credited deposit before calling the payment complete.',
            'production_notes': 'Show a generic receipt and credited balance without personal details.',
            'visual_direction': 'Receipt and receiving-wallet review.',
            'reasoning_summary': 'Receiving-side verification prevents screenshot-only confirmation.',
            'strategy_type': 'directed',
            'hashtags': ['#USDT', '#Freelancer'],
        }
        constraints = {
            'target_audience': 'freelancers and remote workers receiving international payments',
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
        assert plan.content_id == 'directed-' + 'a' * 64
        assert plan.generation_evidence['schema_validated']
        assert plan.generation_evidence['safety_validated']
        assert plan.generation_evidence['constraints_validated']
        assert validate_content_plan(plan) is plan
        for phrase in constraints['must_include']:
            assert phrase in ' '.join((plan.topic, plan.angle, plan.hook, plan.script, plan.cta,
                                      plan.title, plan.description)).lower()
        for phrase in constraints['must_avoid']:
            assert phrase not in ' '.join((plan.topic, plan.angle, plan.hook, plan.script,
                                          plan.cta, plan.title, plan.description)).lower()
        print('FULL_DIRECTED_FIXTURE=PASS')


if __name__ == '__main__':
    main()
