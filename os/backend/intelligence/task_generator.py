from production.tasks.manager import create_task
from production.tasks.models import ProductionTask


def select_provider(task_type: str) -> str:
    """Select execution provider without executing production."""
    if task_type == "ai_video":
        return "ai_gateway"
    return "github"


def generate_production_task(insight):
    """Convert Intelligence Insight into a unified ProductionTask."""

    recommendations = []
    if isinstance(insight, dict):
        recommendations = insight.get("recommendations", []) or []

    text = " ".join(recommendations).lower()

    task_type = "ai_video" if "ai video" in text or "generate video" in text else "video_batch"
    provider = select_provider(task_type)

    task = ProductionTask(
        source="ai_intelligence",
        objective=(
            "create short video about remote payment education"
            if not isinstance(insight, dict)
            else "create content based on intelligence recommendation"
        ),
        provider=provider,
        template="short_video_template",
        parameters={
            "task_type": task_type,
            "insight": insight,
        },
        resources=[],
        priority=0,
    )

    return create_task(task)
