from __future__ import annotations

import json

from assets.manager import get_asset_by_asset_id
from production.runtime.worker import ProductionRuntimeWorker
from production.tasks.manager import create_task, get_task
from production.tasks.models import ProductionTask
from production.tasks.scheduler import schedule_task
from publish.manager import create_publish_task, get_publish_task
from publish.models import PublishTask
from publish.queue import PublishQueue
from publish.worker import PublishWorker


def main():
    task = create_task(
        ProductionTask(
            source="ai_intelligence",
            objective="R2 safe GitHub completion and online asset bridge smoke test",
            provider="github",
            template="os_bridge_test",
            parameters={
                # The bridge workflow is manual-only. Its nested dispatch must
                # explicitly request a fixture artifact so it never recursively
                # launches the bridge driver job.
                "mode": "fixture",
                "github_discover_attempts": 60,
                "github_discover_interval": 1,
                "github_poll_attempts": 180,
                "github_poll_interval": 2,
                "promotion_poll_attempts": 180,
                "promotion_poll_interval": 2,
            },
            resources=[],
            task_type="video_batch",
            workflow="os-github-bridge-test.yml",
            branch="main",
        )
    )
    assert task.id is not None

    job = schedule_task(task)
    assert job["task_id"] == task.id
    assert job["provider"] == "github"

    result = ProductionRuntimeWorker().run(job)
    production_result = result.get("production_result") or {}
    output = production_result.get("output") or {}

    assert result.get("status") == "completed", result
    assert production_result.get("status") == "completed", production_result
    assert output.get("github_run_id"), output
    assert output.get("artifact_id"), output
    assert output.get("asset_url", "").startswith(
        "https://linrui2442-blip.github.io/remote-pay-guide/media/"
    ), output
    assert output.get("storage_type") == "github_pages", output

    task_after = get_task(task.id)
    assert task_after and task_after.status == "completed", task_after

    asset_id = production_result.get("asset_id")
    assert asset_id, production_result
    asset = get_asset_by_asset_id(asset_id)
    assert asset, asset_id
    assert asset.get("source_provider") == "github", asset
    assert asset.get("storage_type") == "github_pages", asset
    assert asset.get("asset_url") == output.get("asset_url"), asset
    assert asset.get("status") == "ready", asset

    publish_task = create_publish_task(
        PublishTask(
            asset_id=asset_id,
            video_id=asset.get("video_id"),
            platform="youtube",
            status="pending",
        )
    )
    persisted = get_publish_task(publish_task["id"])
    assert persisted.get("asset_id") == asset_id, persisted

    worker = PublishWorker(PublishQueue())
    resolved = worker._resolve_asset(persisted)
    assert resolved and resolved.get("asset_url") == asset.get("asset_url"), resolved

    report = {
        "status": "passed",
        "task_id": task.id,
        "runtime_job_id": job["id"],
        "production_result_id": production_result.get("id"),
        "github_run_id": output.get("github_run_id"),
        "github_run_url": output.get("github_run_url"),
        "github_run_conclusion": output.get("github_run_conclusion"),
        "artifact_id": output.get("artifact_id"),
        "artifact_name": output.get("artifact_name"),
        "promotion_run_id": output.get("promotion_run_id"),
        "promotion_run_url": output.get("promotion_run_url"),
        "asset_id": asset_id,
        "asset_url": asset.get("asset_url"),
        "publish_task_id": persisted.get("id"),
        "publish_asset_resolution": resolved.get("asset_url"),
    }
    print("R2_SMOKE_REPORT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
