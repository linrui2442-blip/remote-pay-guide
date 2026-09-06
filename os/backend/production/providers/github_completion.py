from __future__ import annotations

import uuid
from datetime import datetime, timezone

from assets.github_pages import promote_artifact_to_pages
from integrations.github.client import GitHubClient
from production.providers.github_monitor import FAILURE_CONCLUSIONS, GitHubRunMonitor
from production.results.manager import get_result, update_result
from production.tasks.manager import get_task


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def complete_github_execution(result_id, job, client=None):
    """Wait for one GitHub production run, promote its video asset, then finalize Result."""
    client = client or GitHubClient()
    monitor = GitHubRunMonitor(client)
    result = get_result(result_id)
    if not result:
        raise ValueError(f"Production Result {result_id} not found")

    output = dict(result.get("output") or {})
    run_id = output.get("github_run_id")
    if not run_id:
        return update_result(
            result_id,
            status="failed",
            output=output,
            error="GitHub Production Result is missing github_run_id",
        )

    task = get_task(job.get("task_id")) if job else None
    parameters = dict(getattr(task, "parameters", {}) or {})
    poll_interval = max(1, int(parameters.get("github_poll_interval", 10)))
    max_attempts = max(1, int(parameters.get("github_poll_attempts", 720)))

    update_result(
        result_id,
        status="running",
        output={**output, "github_run_status": "running"},
    )

    try:
        terminal = monitor.wait_for_terminal(
            run_id,
            max_attempts=max_attempts,
            poll_interval=poll_interval,
        )
        output.update(
            {
                "github_run_id": run_id,
                "github_run_url": terminal.get("html_url") or output.get("github_run_url"),
                "github_run_status": terminal.get("status"),
                "github_run_conclusion": terminal.get("conclusion"),
                "completed_at": terminal.get("updated_at") or _utc_now(),
            }
        )

        conclusion = terminal.get("conclusion")
        if conclusion != "success":
            error = f"GitHub workflow run {run_id} concluded with {conclusion or 'unknown'}"
            if conclusion in FAILURE_CONCLUSIONS or terminal.get("status") == "completed":
                return update_result(result_id, status="failed", output=output, error=error)
            return update_result(result_id, status="failed", output=output, error=error)

        expected_artifact = parameters.get("artifact_name") or output.get("artifact_name")
        artifact = monitor.discover_artifact(run_id, expected_name=expected_artifact)
        output.update(
            {
                "artifact_id": artifact.get("id"),
                "artifact_name": artifact.get("name"),
                "artifact_size": artifact.get("size_in_bytes"),
                "artifact_expired": artifact.get("expired"),
                "artifact_download_reference": artifact.get("archive_download_url"),
            }
        )

        asset_id = output.get("asset_id") or f"asset_{uuid.uuid4().hex[:8]}"
        asset_filename = parameters.get("asset_filename") or f"task{job.get('task_id')}-{asset_id}.mp4"
        asset_path = parameters.get("asset_path") or ""

        promotion = promote_artifact_to_pages(
            source_run_id=run_id,
            artifact_name=artifact["name"],
            asset_filename=asset_filename,
            asset_path=asset_path,
            client=client,
            monitor=monitor,
            poll_interval=max(1, int(parameters.get("promotion_poll_interval", 5))),
            run_attempts=max(1, int(parameters.get("promotion_poll_attempts", 180))),
            verify_url=True,
        )
        output.update(promotion)
        output["asset_id"] = asset_id

        return update_result(result_id, status="completed", output=output, error=None)
    except Exception as exc:
        output.setdefault("github_run_id", run_id)
        return update_result(result_id, status="failed", output=output, error=str(exc))
