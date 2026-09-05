from typing import Any, Dict

from .models import ProductionTask


def legacy_to_production_task(legacy_task: Dict[str, Any]) -> ProductionTask:
    """Convert legacy task-launch JSON objects into unified ProductionTask.

    This adapter only reads and maps legacy structures. It does not modify
    existing jsonl task files or legacy production workflows.
    """

    return ProductionTask(
        source="legacy",
        objective=legacy_task.get("video_subject", ""),
        provider=legacy_task.get("provider", "github"),
        template=legacy_task.get("video_source", ""),
        parameters={
            "content": legacy_task.get("video_script", ""),
        },
        resources=[legacy_task.get("video_terms")] if legacy_task.get("video_terms") else [],
        status="created",
    )


def ai_to_production_task(ai_task: Dict[str, Any]) -> ProductionTask:
    """Convert future AI Intelligence output into ProductionTask."""

    return ProductionTask(
        source="ai_intelligence",
        objective=ai_task.get("objective", ""),
        provider=ai_task.get("provider", "github"),
        template=ai_task.get("template", ""),
        parameters=ai_task.get("parameters", {}),
        resources=ai_task.get("resources", []),
        priority=ai_task.get("priority", 0),
        status="created",
    )
