from typing import Any, Dict

from .models import ProductionTask


def legacy_to_production_task(
    legacy_task: Dict[str, Any],
    *,
    workflow: str = "",
    branch: str = "main",
) -> ProductionTask:
    """Convert a legacy task-launch record without modifying the source JSONL."""
    return ProductionTask(
        source="legacy",
        objective=legacy_task.get("video_subject", ""),
        provider=legacy_task.get("provider", "github"),
        template=legacy_task.get("video_source", ""),
        parameters={
            "content": legacy_task.get("video_script", ""),
            "legacy_video_config": {
                key: value
                for key, value in legacy_task.items()
                if key not in {"video_subject", "video_script", "video_terms"}
            },
        },
        resources=legacy_task.get("video_terms", []) or [],
        task_type=legacy_task.get("task_type", "video_batch"),
        workflow=legacy_task.get("workflow", workflow),
        branch=legacy_task.get("branch", branch),
        status="created",
    )


def ai_to_production_task(ai_task: Dict[str, Any]) -> ProductionTask:
    """Convert AI Intelligence output into the canonical ProductionTask."""
    return ProductionTask(
        source="ai_intelligence",
        objective=ai_task.get("objective", ""),
        provider=ai_task.get("provider", "github"),
        template=ai_task.get("template", ""),
        parameters=ai_task.get("parameters", {}),
        resources=ai_task.get("resources", []),
        priority=ai_task.get("priority", 0),
        task_type=ai_task.get("task_type", ""),
        workflow=ai_task.get("workflow", ""),
        branch=ai_task.get("branch", "main"),
        status="created",
    )
