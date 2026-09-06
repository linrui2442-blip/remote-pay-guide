from dataclasses import asdict, is_dataclass

from production.tasks.manager import create_task
from production.tasks.models import ProductionTask


def select_provider(task_type: str) -> str:
    """Select execution provider without executing production."""
    if task_type == "ai_video":
        return "ai_gateway"
    return "github"


def _to_dict(value):
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    return {}


def generate_production_task(insight):
    """Convert Intelligence Insight or ProductionStrategy into ProductionTask."""
    data = _to_dict(insight)

    recommendations = data.get("recommendations", []) or []
    parameters = dict(data.get("parameters", {}) or {})
    if not recommendations:
        recommendations = parameters.get("recommendations", []) or []

    text = " ".join(str(item) for item in recommendations).lower()
    task_type = parameters.get("task_type")
    if not task_type:
        task_type = "ai_video" if "ai video" in text or "generate video" in text else "video_batch"

    suggested_provider = data.get("provider_suggestion")
    provider = (
        suggested_provider
        if suggested_provider in {"github", "ai_gateway"}
        else select_provider(task_type)
    )

    objective = data.get("objective") or (
        "create content based on intelligence recommendation"
        if data
        else "create short video about remote payment education"
    )
    template = data.get("template_recommendation") or data.get("template") or "short_video_template"
    resources = data.get("resources", []) or []

    parameters.setdefault("task_type", task_type)
    parameters.setdefault("intelligence_input", data or insight)

    task = ProductionTask(
        source="ai_intelligence",
        objective=objective,
        provider=provider,
        template=template,
        parameters=parameters,
        resources=resources,
        priority=0,
    )

    return create_task(task)
