from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from accounts.manager import get_account
from assets.manager import get_asset, get_asset_by_asset_id
from publish.manager import create_publish_task, get_publish_task, get_publish_tasks
from publish.models import PublishTask
from publish.queue import PublishQueue
from publish.registry import get_adapter
from publish.worker import PublishWorker


class PublishContractError(RuntimeError):
    """Raised when a Publish Center action is not safe/ready to execute."""


def _normalize_platform(value):
    normalized = str(value or "").strip().lower()
    if not normalized:
        raise PublishContractError("PublishTask platform is required")
    return normalized


def get_publish_execution_readiness(platform):
    """Return adapter-level readiness without claiming account credentials are ready."""
    normalized = _normalize_platform(platform)
    adapter = get_adapter(normalized)
    if adapter is None:
        return {
            "platform": normalized,
            "adapter_registered": False,
            "publish_ready": False,
            "execution_mode": "unavailable",
            "reason": "publish adapter is not registered",
        }

    raw_status = adapter.get_status() if hasattr(adapter, "get_status") else {}
    status = raw_status if isinstance(raw_status, dict) else {"status": raw_status}
    publish_ready = status.get("publish_ready")
    if publish_ready is None:
        publish_ready = status.get("status") == "ready"

    execution_mode = status.get("execution_mode") or (
        "live" if publish_ready else "unavailable"
    )
    reason = status.get("reason")
    if not publish_ready and not reason:
        reason = f"{normalized} adapter is not enabled for live OS publishing"

    return {
        "platform": normalized,
        "adapter_registered": True,
        "adapter": adapter.__class__.__name__,
        "status": status.get("status"),
        "publish_ready": bool(publish_ready),
        "execution_mode": execution_mode,
        "reason": reason,
    }


def _resolve_asset(task: PublishTask):
    asset = None
    if task.asset_id:
        asset = get_asset_by_asset_id(task.asset_id)
    elif task.video_id:
        asset = get_asset(task.video_id)

    if not asset:
        raise PublishContractError("video asset not found")

    if str(asset.get("status") or "").lower() != "ready":
        raise PublishContractError(
            f"video asset {asset.get('asset_id') or task.asset_id or task.video_id} is not ready"
        )

    asset_url = asset.get("asset_url")
    file_path = asset.get("file_path")
    location = asset.get("location")
    if file_path and not Path(file_path).is_file():
        raise PublishContractError(f"video asset local file does not exist: {file_path}")
    if not asset_url and not file_path and not location:
        raise PublishContractError("video asset has no resolvable location")
    return asset


def _validate_account(task: PublishTask, platform: str):
    if task.account_id is None:
        raise PublishContractError("PublishTask account_id is required")
    account = get_account(task.account_id)
    if not account:
        raise PublishContractError(f"account_id {task.account_id} was not found")
    account_platform = str(account.get("platform") or "").strip().lower()
    if account_platform != platform:
        raise PublishContractError(
            f"account_id {task.account_id} is bound to {account_platform or 'unknown'}, not {platform}"
        )
    return account


def _validate_publish_contract(task: PublishTask):
    platform = _normalize_platform(task.platform)
    readiness = get_publish_execution_readiness(platform)
    if not readiness["publish_ready"]:
        raise PublishContractError(readiness["reason"])
    account = _validate_account(task, platform)
    asset = _resolve_asset(task)
    return platform, readiness, account, asset


def _find_existing_task(task: PublishTask, platform: str):
    active_statuses = {"pending", "publishing", "published"}
    for current in reversed(get_publish_tasks()):
        if str(current.get("platform") or "").lower() != platform:
            continue
        if current.get("account_id") != task.account_id:
            continue
        if str(current.get("status") or "").lower() not in active_statuses:
            continue
        if task.asset_id and current.get("asset_id") == task.asset_id:
            return current
        if not task.asset_id and task.video_id and current.get("video_id") == task.video_id:
            return current
    return None


def prepare_publish_task(task):
    """Validate and persist a publish task without performing any external upload."""
    payload = task if isinstance(task, PublishTask) else PublishTask(**dict(task))
    platform, readiness, account, asset = _validate_publish_contract(payload)

    existing = _find_existing_task(payload, platform)
    if existing:
        return {
            "created": False,
            "task": existing,
            "readiness": readiness,
            "account": account,
            "asset_id": asset.get("asset_id"),
        }

    payload.platform = platform
    payload.status = "pending"
    if not payload.asset_id:
        payload.asset_id = asset.get("asset_id")
    if not payload.video_id:
        payload.video_id = asset.get("video_id")
    created = create_publish_task(payload)
    return {
        "created": True,
        "task": created,
        "readiness": readiness,
        "account": account,
        "asset_id": asset.get("asset_id"),
    }


def _future_scheduled_time(value):
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PublishContractError("PublishTask scheduled_time is not valid ISO 8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc) > datetime.now(timezone.utc)


def execute_publish_task(task_id, *, queue=None, worker_factory=PublishWorker):
    """Execute one explicitly requested PublishTask through the registered adapter."""
    stored = get_publish_task(task_id)
    if not stored:
        raise PublishContractError("publish task not found")

    status = str(stored.get("status") or "").lower()
    if status not in {"pending", "failed"}:
        raise PublishContractError(
            f"publish task status {status or 'unknown'} cannot be executed"
        )
    if _future_scheduled_time(stored.get("scheduled_time")):
        raise PublishContractError("publish task is scheduled for a future time")

    payload = PublishTask(**stored)
    _validate_publish_contract(payload)

    publish_queue = queue or PublishQueue()
    publish_queue.add_task(task_id)
    worker = worker_factory(publish_queue)
    worker_result = worker.run_once()
    current = get_publish_task(task_id)
    return {
        "task": current,
        "worker": worker_result,
        "executed": bool(worker_result.get("processed")),
    }
