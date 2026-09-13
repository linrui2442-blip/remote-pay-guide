from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass
class ContentPlan:
    content_id: str
    topic: str
    angle: str
    target_audience: str
    hook: str
    script: str
    cta: str
    title: str
    description: str
    hashtags: List[str] = field(default_factory=list)
    production_notes: str = ""
    visual_direction: str = ""
    reasoning_summary: str = ""
    source_snapshot_id: Any = None
    source_content_id: str | None = None
    strategy_type: str = "iterate"
    novelty_status: str = "unverified"
    novelty_evidence: Dict[str, Any] = field(default_factory=dict)
    production_spec: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def build_content_brain_prompt(snapshot, strategy, history=None, production_history=None, novelty_history=None):
    return """You are the Remote Pay Guide content planner. Audience: freelancer, remote worker, digital nomad, overseas service provider, and first-time stablecoin payment receiver. Funnel: Short video -> Profile/Bio -> Remote Pay Guide -> stablecoin payment education -> Binance referral click. Never give investment advice, price prediction, trading recommendations, seed phrase/private key requests, or unsafe crypto instructions. Preserve effective variables, test a limited explicit variable, and explain preserved_variable, tested_variable, and why. Do not copy recent topics, hooks, angles, or visual plans.\n\nDATA CENTER SNAPSHOT:\n{snapshot}\nSTRATEGY:\n{strategy}\nRECENT CONTENT:\n{history}\nRECENT PRODUCTION:\n{production_history}\nRECENT NOVELTY:\n{novelty_history}""".format(snapshot=snapshot, strategy=strategy, history=history or [], production_history=production_history or [], novelty_history=novelty_history or [])


class ContentPlanProvider(Protocol):
    def generate_content_plan(self, snapshot, context) -> ContentPlan: ...


class DeterministicContentPlanProvider:
    def generate_content_plan(self, snapshot, context):
        return ContentPlan(
            content_id="plan-preview",
            topic="Verify a stablecoin payment arrived",
            angle="payment verification before declaring work paid",
            target_audience="freelancers and remote workers",
            hook="A payment screenshot is not proof that your money arrived.",
            script="Open the account that actually receives the deposit, check balance and deposit history, then confirm the transaction is credited.",
            cta="Follow Remote Pay Guide for safer payment workflows.",
            title="How to Verify a Stablecoin Payment Arrived",
            description="A practical receiving-side check for freelancers.",
            hashtags=["#Stablecoin", "#Freelancer", "#RemoteWork"],
            reasoning_summary="Keep the receiving-side education signal while testing a verification step.",
            source_snapshot_id=snapshot.get("id") if isinstance(snapshot, dict) else None,
            strategy_type="iterate",
            novelty_status="preview",
            production_spec={"provider": "github", "workflow": "render-short01.yml", "branch": "main"},
        )
