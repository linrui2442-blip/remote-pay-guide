import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai.models import AIRequest
from intelligence.content_brain import (
    ContentPlan,
    ContentPlanGenerationError,
    LLMContentPlanProvider,
    validate_content_plan,
)


GOOD = {
    "topic": "Stablecoin payment verification",
    "angle": "Verify receipt before treating the payment as complete",
    "target_audience": "first-time stablecoin receiving freelancers",
    "hook": "A payment screenshot is not enough.",
    "script": "Verify the actual receiving account and check deposit history. Never share your seed phrase or private key with anyone.",
    "cta": "Use Remote Pay Guide for a safer receiving workflow.",
    "title": "Verify payment",
    "description": "Safe payment education.",
    "production_notes": "Practical receiving-side checks.",
    "visual_direction": "Receipt and account review.",
    "reasoning_summary": "Prioritize safe verification.",
    "strategy_type": "directed",
    "hashtags": ["#stablecoin"],
}


class FakeText:
    def __init__(self, text):
        self.text = text
        self.call_count = 0
        self.model = "test-model"

    def readiness(self):
        return {"runtime_ready": True, "missing_configuration": []}

    def request(self, request: AIRequest):
        self.call_count += 1
        return {"output": json.dumps(self.text)}


def provider_with_script(script):
    payload = dict(GOOD)
    payload["script"] = script
    return LLMContentPlanProvider(FakeText(payload))


safe = provider_with_script("Verify the actual receiving account and check deposit history. Never share your seed phrase or private key with anyone.")
safe_plan = safe.generate_content_plan({"id": 1}, {})
assert safe.text_provider.call_count == 1
assert safe_plan.script.startswith("Verify the actual receiving account")
print("SAFE_GENERATED_NEGATION_FULL_PROVIDER_PATH=PASS")

final_plan = ContentPlan(
    content_id="g2b8-final",
    topic="Payment verification",
    angle="Receiving-side check",
    target_audience="freelancers",
    hook="Check before calling it paid.",
    script="Never share your seed phrase or private key.",
    cta="Follow Remote Pay Guide.",
    title="Verify payment",
    description="Safe education.",
    production_spec={},
)
validate_content_plan(final_plan)
print("SAFE_NEGATION_FINAL_PLAN_VALIDATION=PASS")
unsafe_final = ContentPlan(**{**final_plan.to_dict(), "content_id": "g2b8-unsafe-final", "script": "Never share your seed phrase, but send me your private key."})
try:
    validate_content_plan(unsafe_final)
except ValueError:
    print("FINAL_PLAN_OCCURRENCE_LOCAL_SAFETY=PASS")
else:
    raise AssertionError("unsafe final plan was accepted")

for marker, script in (
    ("UNSAFE_SEED_PHRASE_OUTPUT_BLOCKED", "Send me your seed phrase so I can verify the payment."),
    ("UNSAFE_PRIVATE_KEY_OUTPUT_BLOCKED", "Share your private key so I can check the wallet."),
    ("UNSAFE_TRADING_RECOMMENDATION_BLOCKED", "Here is my trading recommendation: buy this token."),
    ("UNSAFE_GUARANTEED_RETURNS_BLOCKED", "We guarantee returns from this strategy."),
):
    blocked = provider_with_script(script)
    try:
        blocked.generate_content_plan({"id": 1}, {})
    except ContentPlanGenerationError:
        print(marker + "=PASS")
    else:
        raise AssertionError(marker + " was accepted")

safe_trading = provider_with_script("Do not give trading recommendations or price predictions.")
safe_trading.generate_content_plan({"id": 1}, {})
print("SAFE_TRADING_PROHIBITION_ALLOWED=PASS")

safe_returns = provider_with_script("Never promise guaranteed returns.")
safe_returns.generate_content_plan({"id": 1}, {})
print("SAFE_GUARANTEED_RETURNS_WARNING_ALLOWED=PASS")

for mixed in (
    "Never share your seed phrase. Send me your private key.",
    "Do not give trading recommendations. Here is my trading recommendation: buy X.",
):
    try:
        provider_with_script(mixed).generate_content_plan({"id": 1}, {})
    except ContentPlanGenerationError:
        pass
    else:
        raise AssertionError("mixed safe/unsafe content was accepted")
print("MIXED_SAFE_UNSAFE_CONTENT_BLOCKED=PASS")

for marker, mixed in (
    ("SAME_SENTENCE_SEED_PRIVATE_KEY_MIXED_BLOCKED", "Never share your seed phrase, but send me your private key."),
    ("SAME_SENTENCE_TRADING_MIXED_BLOCKED", "Do not give trading recommendations, but my trading recommendation is buy X."),
    ("SAME_SENTENCE_RETURNS_MIXED_BLOCKED", "Never promise guaranteed returns, but this strategy guarantees returns."),
    ("NEXT_SENTENCE_NEGATION_DOES_NOT_BLEED", "Never share your seed phrase. Send me your private key."),
    ("DISTANT_NEGATION_WINDOW_DOES_NOT_BLEED", "Never share your seed phrase. This guide explains payment confirmation. If you need help, send me your private key."),
    ("LATE_NEGATION_DOES_NOT_RESCUE_UNSAFE_OCCURRENCE", "Send me your private key, but do not share it with anyone else."),
):
    try:
        provider_with_script(mixed).generate_content_plan({"id": 1}, {})
    except ContentPlanGenerationError:
        print(marker + "=PASS")
    else:
        raise AssertionError(marker + " was accepted")

for safe_text in (
    "Never share your seed phrase.",
    "Do not share your private key.",
    "A legitimate service should never ask for your seed phrase.",
    "Do not give trading recommendations.",
    "Avoid price prediction.",
    "Never promise guaranteed returns.",
):
    provider_with_script(safe_text).generate_content_plan({"id": 1}, {})
print("SAFE_NEGATION_CASES_STILL_ALLOWED=PASS")

# Exercise the registered route handler with a fake transport and isolated DB.
import routers.intelligence as intelligence_router

original_provider = intelligence_router.select_content_plan_provider
original_snapshot = intelligence_router.get_feedback_snapshot
route_provider = provider_with_script("Verify the actual receiving account. Never share your seed phrase or private key.")
intelligence_router.select_content_plan_provider = lambda: route_provider
intelligence_router.get_feedback_snapshot = lambda snapshot_id: {"id": snapshot_id, "content_id": "g2b8-route"}
try:
    from routers.intelligence import ContentPlanGenerationRequest, generate_content_plan
    response = generate_content_plan(1, ContentPlanGenerationRequest(human_brief="Verify a payment safely.", human_constraints={}))
    assert response["plan"]["status"] == "preview"
    assert response["plan"]["plan"]["generation_mode"] == "directed"
    print("SAFE_NEGATION_CANONICAL_ROUTE=PASS")
finally:
    intelligence_router.select_content_plan_provider = original_provider
    intelligence_router.get_feedback_snapshot = original_snapshot

print("G2B7_FAILURE_CLASS_OFFLINE_REGRESSION=PASS")
