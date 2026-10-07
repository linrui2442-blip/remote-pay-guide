from __future__ import annotations

import json
from datetime import datetime, timezone

from assets.github_pages import promote_artifact_to_pages, poll_claimed_promotion, _verify_public_url
from integrations.github.client import GitHubClient
from production.providers.github_monitor import FAILURE_CONCLUSIONS, GitHubRunMonitor
from production.results.manager import claim_result_for_completion, get_result, update_result
from production.tasks.manager import get_task


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def complete_github_execution(result_id, job, client=None, *, human_authorized_resume=False):
    """Wait for one GitHub production run, promote its video asset, then finalize Result."""
    client = client or GitHubClient()
    monitor = GitHubRunMonitor(client)
    result = get_result(result_id)
    if not result:
        raise ValueError(f"Production Result {result_id} not found")

    if result.get('status') in {'completed', 'failed'}:
        return result
    from production.runtime.manager import get_job
    persisted_job = get_job((job or {}).get('id'))
    if not persisted_job or persisted_job['id'] != result['runtime_job_id'] or persisted_job['task_id'] != job.get('task_id') or persisted_job['provider'] != 'github':
        raise ValueError('Manual completion requires the linked RuntimeJob')

    output = dict(result.get("output") or {})
    run_id = output.get("github_run_id")
    if not run_id:
        return update_result(
            result_id,
            status="failed",
            output=output,
            error="GitHub Production Result is missing github_run_id",
        )

    if result.get("status") in {"completed", "failed"}:
        return result
    if not claim_result_for_completion(result_id) and not result.get('promotion_state'):
        return get_result(result_id)

    task = get_task(job.get("task_id")) if job else None
    parameters = dict(getattr(task, "parameters", {}) or {})
    if parameters.get('production_routing'):
        output['g4b_no_asset_binding'] = True
    poll_interval = max(1, int(parameters.get("github_poll_interval", 10)))
    max_attempts = max(1, int(parameters.get("github_poll_attempts", 720)))

    current = get_result(result_id)
    if current['status'] in {'completed','failed'}:
        return current
    if task and task.status == 'scheduled':
        from production.tasks.scheduler import transition_task
        transition_task(task, 'running')

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

        asset_id = output.get("asset_id") or f"asset_github_result_{result_id}"
        asset_filename = parameters.get("asset_filename") or f"task{job.get('task_id')}-{asset_id}.mp4"
        asset_path = parameters.get("asset_path") or "final-output.mp4"
        parameters.update(asset_path=asset_path, asset_filename=asset_filename)
        promotion = poll_claimed_promotion(result_id=result_id, job=job, source_run_id=run_id,
            artifact=artifact, parameters=parameters, client=client, monitor=monitor, promoter=promote_artifact_to_pages,
            human_authorized_resume=human_authorized_resume)
        if promotion['status'] == 'running' and promotion['output'].get('promotion_run_id'):
            monitor.wait_for_terminal(promotion['output']['promotion_run_id'],
                max_attempts=max(1, int(parameters.get('promotion_poll_attempts', 180))),
                poll_interval=max(1, int(parameters.get('promotion_poll_interval', 5))))
            promotion = poll_claimed_promotion(result_id=result_id, job=job, source_run_id=run_id,
                artifact=artifact, parameters=parameters, client=client, monitor=monitor, promoter=promote_artifact_to_pages,
                human_authorized_resume=human_authorized_resume)
        output.update(promotion['output'])
        output["asset_id"] = asset_id
        if promotion['status'] == 'completed':
            _verify_public_url(output['asset_url'])
        return update_result(result_id, status=promotion['status'], output=output, error=promotion.get('error'))
    except Exception as exc:
        output.setdefault("github_run_id", run_id)
        try:
            current = get_result(result_id)
            if current and current.get("promotion_state") in {"intent", "submitted", "running"}:
                if human_authorized_resume:
                    if str(exc) == "Promotion dispatch outcome is ambiguous":
                        bounded_error = "PROMOTION_DISPATCH_OUTCOME_AMBIGUOUS"
                    try:
                        promotion_metadata = json.loads(current.get("promotion_metadata") or "{}")
                    except (TypeError, ValueError, json.JSONDecodeError):
                        promotion_metadata = {}
                    if promotion_metadata.get("recovery_required"):
                        bounded_error = "PROMOTION_POST_OUTCOME_REQUIRES_RECOVERY"
                    elif str(exc) != "Promotion dispatch outcome is ambiguous":
                        bounded_error = "HUMAN_PROMOTION_RESUME_FAILED"
                    # Keep the durable recovery state untouched and return a
                    # secret-safe diagnostic to the explicit human caller.
                    returned = dict(current)
                    returned["error"] = bounded_error
                    return returned
                # A failure after intent/POST is recoverable state, not a
                # license to issue another POST. Keep the result running so a
                # restart can correlate the exact remote run and finalize it.
                return get_result(result_id)
        except Exception:
            pass
        return update_result(result_id, status="failed", output=output, error=str(exc))


def continue_human_authorized_github_completion(result_id, *, client=None):
    """Explicit human invocation for one already-claimed routed promotion."""
    from production.runtime.manager import get_job
    from intelligence.content_brain import get_plan

    result = get_result(result_id)
    if not result or result.get('provider') != 'github' or result.get('status') not in {'running', 'completed'}:
        raise ValueError('Running or completed GitHub ProductionResult required')
    if result.get('promotion_state') not in {'intent', 'submitted', 'running', 'completed'}:
        raise ValueError('Recoverable promotion intent required')
    job = get_job(result['runtime_job_id'])
    task = get_task(job.get('task_id')) if job else None
    if not job or job.get('provider') != 'github' or job.get('job_type') != 'github_runtime' or not task or task.provider != 'github':
        raise ValueError('GitHub result/job/task linkage invalid')
    parameters = task.parameters or {}
    route = parameters.get('production_routing') or {}
    plan_id = parameters.get('content_plan_id')
    plan = get_plan(plan_id) if plan_id else None
    if not plan or plan.get('status') != 'materialized' or plan.get('revision') != parameters.get('content_plan_revision'):
        raise ValueError('Current materialized ContentPlan required')
    from intelligence.content_plan_service import _validate_materialized_task
    key = f"content-plan:{plan_id}:revision:{plan['revision']}"
    _validate_materialized_task(task, plan_id, plan['revision'], key)
    expected_status = result['status']
    if route.get('selected_provider') != 'github' or task.status != expected_status or job.get('status') != expected_status:
        raise ValueError('Human GitHub continuation state mismatch')
    intent = json.loads(result.get('promotion_metadata') or '{}')
    if (intent.get('production_result_id') != result_id or intent.get('runtime_job_id') != job['id'] or
        intent.get('source_run_id') != (result.get('output') or {}).get('github_run_id') or
        intent.get('workflow') != 'promote-video-asset.yml' or intent.get('branch') != 'main'):
        raise ValueError('Persisted promotion correlation invalid')
    if result['status'] == 'completed':
        if result['promotion_state'] != 'completed' or not (result.get('output') or {}).get('g4b_no_asset_binding'):
            raise ValueError('Completed result violates the G4-D asset boundary')
        return result
    if result.get('asset_id'):
        raise ValueError('Unfinished promotion has an asset binding')
    return complete_github_execution(result_id, job, client=client, human_authorized_resume=True)
