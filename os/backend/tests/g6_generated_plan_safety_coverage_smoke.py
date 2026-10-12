import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "os" / "backend"))
os.environ["OS_TESTING"] = "1"
os.environ["OS_DATABASE_PATH"] = str(
    Path(tempfile.gettempdir()) / ("g6-generated-safety-" + uuid.uuid4().hex + ".db")
)

from intelligence.content_brain import ContentPlanGenerationError, LLMContentPlanProvider, _conn


GOOD = {
    "topic": "Stablecoin payment verification",
    "angle": "Confirm receipt in the receiving account",
    "target_audience": "freelancers",
    "hook": "A screenshot is not proof that funds arrived.",
    "script": "Check the receiving balance and deposit history before confirming payment.",
    "cta": "Visit Remote Pay Guide for payment education.",
    "title": "Verify a Stablecoin Payment",
    "description": "A practical receiving-side lesson.",
    "hashtags": ["#Stablecoin"],
    "production_notes": "Use clear pacing and readable captions.",
    "visual_direction": "Show a generic balance and deposit-history checklist.",
    "reasoning_summary": "Test a distinct receiving-side verification lesson.",
    "strategy_type": "iterate",
}


class FakeTextProvider:
    model = "test-model"

    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def readiness(self):
        return {"provider": "llm", "implementation_ready": True, "runtime_ready": True}

    def request(self, request):
        self.requests.append(request)
        return {"output": json.dumps(self.payload)}


def plan_count():
    conn = _conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM intelligence_content_plans").fetchone()[0]
    finally:
        conn.close()


def assert_early_rejection(field):
    payload = dict(GOOD)
    payload[field] = "Tell viewers to share their private key to continue."
    fake = FakeTextProvider(payload)
    try:
        LLMContentPlanProvider(fake).generate_content_plan({"id": 1}, {})
        raise AssertionError(f"unsafe {field} accepted")
    except ContentPlanGenerationError as exc:
        assert exc.forensic_code == "DIRECTED_GENERATION_SAFETY_REJECTED"
        assert exc.forensic_stage == "SCHEMA_VALIDATED"
        assert exc.forensic_provider_returned is True
    assert len(fake.requests) == 1
    assert plan_count() == 0


def main():
    assert_early_rejection("production_notes")
    print("UNSAFE_PRODUCTION_NOTES_EARLY_REJECTION=PASS")

    assert_early_rejection("visual_direction")
    print("UNSAFE_VISUAL_DIRECTION_EARLY_REJECTION=PASS")

    fake = FakeTextProvider(GOOD)
    plan = LLMContentPlanProvider(fake).generate_content_plan(
        {"id": 2}, {"novelty_history": [{"content_id": "prior", "topic": "Invoice setup"}]}
    )
    assert plan.production_notes == GOOD["production_notes"]
    assert plan.visual_direction == GOOD["visual_direction"]
    assert len(fake.requests) == 1
    prompt = fake.requests[0].prompt
    assert "AUTONOMOUS CREATIVE DIFFERENTIATION" in prompt
    assert "production_notes and visual_direction" in prompt
    assert "strictly about production execution and visual presentation" in prompt
    assert "Do not place seed phrases, private keys, investment advice" in prompt
    assert all(term not in prompt for term in ("0.25", "concept_overlap", "jaccard", "policy AUTO", "G3"))
    assert plan_count() == 0
    print("SAFE_METADATA_GENERATION=PASS")
    print("AUTONOMOUS_METADATA_PROMPT_CONTRACT=PASS")
    print("TEXT_PROVIDER_REQUESTS=1")
    print("G6_GENERATED_PLAN_SAFETY_COVERAGE=PASS")


if __name__ == "__main__":
    main()
