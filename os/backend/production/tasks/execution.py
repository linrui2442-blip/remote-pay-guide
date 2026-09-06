from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict


VIDEO_TASK_TYPES = {"ai_video", "ai_generated_video", "video_generation"}


def _to_dict(task: Any) -> Dict[str, Any]:
    if isinstance(task, dict):
        return dict(task)
    if is_dataclass(task):
        return asdict(task)
    if hasattr(task, "model_dump"):
        return task.model_dump()
    if hasattr(task, "dict"):
        return task.dict()
    return {}


def get_execution_readiness(task: Any) -> Dict[str, Any]:
    """Return provider-specific execution readiness without mutating state.

    This function deliberately validates only the ProductionTask execution
    contract. External credential/network readiness remains the provider's
    responsibility and can be reported separately by the provider registry.
    """
    data = _to_dict(task)
    provider = str(data.get("provider") or "").strip().lower()
    parameters = data.get("parameters") or {}
    if not isinstance(parameters, dict):
        parameters = {}

    task_type = str(
        data.get("task_type") or parameters.get("task_type") or ""
    ).strip()
    workflow = str(
        data.get("workflow") or parameters.get("workflow") or ""
    ).strip()
    branch = str(data.get("branch") or parameters.get("branch") or "main").strip()

    missing = []
    warnings = []

    if provider == "github":
        if not workflow:
            missing.append("workflow")
        if not branch:
            missing.append("branch")
    elif provider == "ai_gateway":
        if not task_type:
            missing.append("task_type")
        elif task_type not in VIDEO_TASK_TYPES:
            warnings.append(
                "AI Gateway Production is intended for remote video-generation tasks"
            )
    else:
        missing.append("registered provider")

    ready = not missing
    if ready:
        reason = None
    elif provider == "github" and "workflow" in missing:
        reason = (
            "GitHub Production requires an explicit workflow; no legacy render "
            "workflow is guessed automatically"
        )
    elif provider == "ai_gateway" and "task_type" in missing:
        reason = "AI Gateway Production requires a task_type"
    else:
        reason = "ProductionTask execution contract is incomplete"

    return {
        "ready": ready,
        "provider": provider or None,
        "task_type": task_type or None,
        "workflow": workflow or None,
        "branch": branch or None,
        "missing": missing,
        "warnings": warnings,
        "reason": reason,
    }


def require_execution_ready(task: Any) -> Dict[str, Any]:
    readiness = get_execution_readiness(task)
    if readiness["ready"]:
        return readiness

    detail = readiness.get("reason") or "ProductionTask is not executable"
    missing = readiness.get("missing") or []
    if missing:
        detail = f"{detail}. Missing: {', '.join(missing)}"
    raise ValueError(detail)
