from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List


@dataclass
class ProductionStrategy:
    objective: str
    topic_direction: str
    template_recommendation: str
    provider_suggestion: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    resources: List[Any] = field(default_factory=list)
    reasoning_summary: str = ""


def _to_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    return {}


def build_production_strategy(feedback_insight: Any) -> ProductionStrategy:
    """Translate a FeedbackInsight into a production recommendation only.

    This layer never executes providers, creates runtime jobs, or triggers
    production. It only prepares the strategy consumed by the existing task
    generator.
    """
    feedback = _to_dict(feedback_insight)
    score = int(feedback.get("performance_score", 0) or 0)
    recommendations = feedback.get("recommendations", []) or []
    successful_patterns = feedback.get("successful_patterns", []) or []
    weak_patterns = feedback.get("weak_patterns", []) or []
    video_id = feedback.get("video_id")

    recommendation_text = " ".join(str(item) for item in recommendations).lower()
    provider_suggestion = (
        "ai_gateway"
        if "ai video" in recommendation_text or "ai-generated video" in recommendation_text
        else "github"
    )

    if score >= 75:
        objective = "produce a follow-up video that extends the strongest observed performance patterns"
        topic_direction = "continue the strongest proven content direction"
        strategy_type = "scale_winner"
        summary = "High performance: preserve successful elements and produce a controlled follow-up."
    elif score <= 25:
        objective = "produce a revised video that tests a different topic angle or template"
        topic_direction = "adjust the content angle before repeating the current pattern"
        strategy_type = "revise_underperformer"
        summary = "Low performance: change one or more content variables before repeating the format."
    else:
        objective = "produce a controlled iteration using the strongest available feedback signals"
        topic_direction = "retain strong elements while testing one production variable"
        strategy_type = "iterate"
        summary = "Mixed performance: keep useful signals and test a limited change."

    return ProductionStrategy(
        objective=objective,
        topic_direction=topic_direction,
        template_recommendation="short_video_template",
        provider_suggestion=provider_suggestion,
        parameters={
            "strategy_type": strategy_type,
            "performance_score": score,
            "successful_patterns": successful_patterns,
            "weak_patterns": weak_patterns,
            "recommendations": recommendations,
        },
        resources=[video_id] if video_id else [],
        reasoning_summary=summary,
    )
