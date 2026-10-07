from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import requests

from integrations.github.client import GitHubClient
from production.providers.github_monitor import GitHubRunMonitor


PROMOTION_WORKFLOW = "promote-video-asset.yml"
ASSET_FILE_RE = re.compile(r"^[A-Za-z0-9._-]+\.mp4$")


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _public_url(client, asset_filename):
    return f"https://{client.owner}.github.io/{client.repo}/media/{asset_filename}"


def _verify_public_url(url, max_attempts=24, poll_interval=5, session=None):
    """Verify a public direct video response without exposing sensitive errors."""
    parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(url or "")
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("public asset URL must be an absolute https URL")
    http = session or requests
    last_error = None
    for _ in range(max_attempts):
        try:
            response = http.head(url, allow_redirects=True, timeout=15)
            final_url = response.url or url
            final = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(final_url)
            content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            content_length = response.headers.get("Content-Length")
            non_empty = content_length is None or int(content_length) > 0
            valid_type = content_type.startswith("video/") or (
                not content_type and final.path.lower().endswith(".mp4")
            )
            if response.status_code < 400 and final.scheme == "https" and non_empty and valid_type:
                return True
            if response.status_code in {405, 501}:
                response.close()
                response = http.get(
                    url, allow_redirects=True, timeout=15,
                    headers={"Range": "bytes=0-0"}, stream=True,
                )
                final = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(response.url or url)
                content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
                if response.status_code < 400 and final.scheme == "https" and content_type.startswith("video/"):
                    return True
            last_error = f"HTTP {response.status_code}"
            response.close()
        except requests.RequestException as exc:
            last_error = type(exc).__name__
        except (TypeError, ValueError):
            last_error = "invalid media response"
        time.sleep(poll_interval)
    raise TimeoutError(f"GitHub Pages URL did not become a valid media response ({last_error})")


def promote_artifact_to_pages(
    *,
    source_run_id,
    artifact_name,
    asset_filename,
    asset_path="",
    client=None,
    monitor=None,
    discover_attempts=30,
    poll_interval=2,
    run_attempts=180,
    verify_url=True,
    pre_dispatch_run_ids=None,
    submitted_at=None,
    dispatch_only=False,
):
    client = client or GitHubClient()
    monitor = monitor or GitHubRunMonitor(client)

    if not ASSET_FILE_RE.fullmatch(asset_filename or ""):
        raise ValueError("asset_filename must be a simple unique .mp4 filename")

    pre_ids = monitor.snapshot_run_ids(PROMOTION_WORKFLOW, "main") if pre_dispatch_run_ids is None else pre_dispatch_run_ids
    submitted_at = submitted_at or _utc_now()
    client.trigger_workflow(
        workflow=PROMOTION_WORKFLOW,
        branch="main",
        inputs={
            "source_run_id": str(source_run_id),
            "artifact_name": str(artifact_name),
            "asset_path": str(asset_path or ""),
            "asset_filename": asset_filename,
        },
    )
    run = monitor.discover_run(
        PROMOTION_WORKFLOW,
        "main",
        pre_ids,
        submitted_at,
        max_attempts=discover_attempts,
        poll_interval=poll_interval,
    )
    if dispatch_only:
        return {'promotion_run_id': run['id'], 'promotion_run_url': run.get('html_url'), 'promotion_run_status': run.get('status'), 'promotion_run_conclusion': run.get('conclusion')}
    terminal = monitor.wait_for_terminal(
        run["id"],
        max_attempts=run_attempts,
        poll_interval=poll_interval,
    )
    if terminal.get("conclusion") != "success":
        raise RuntimeError(
            f"Asset promotion workflow failed: run={run['id']} "
            f"conclusion={terminal.get('conclusion')}"
        )

    url = _public_url(client, asset_filename)
    if verify_url:
        _verify_public_url(url)

    return {
        "promotion_run_id": run["id"],
        "promotion_run_url": run.get("html_url"),
        "promotion_run_status": terminal.get("status"),
        "promotion_run_conclusion": terminal.get("conclusion"),
        "promotion_submitted_at": submitted_at,
        "promotion_completed_at": terminal.get("updated_at"),
        "storage_type": "github_pages",
        "asset_url": url,
        "asset_filename": asset_filename,
        "asset_ready": True,
    }


def poll_claimed_promotion(*, result_id, job, source_run_id, artifact, parameters, client, monitor, promoter=None,
                           human_authorized_resume=False):
    """Shared durable one-POST boundary; only an explicit human resume may POST an old intent."""
    import json
    from production.results.manager import (get_result, claim_promotion_execution,
                                            claim_human_promotion_resume, update_promotion_state)
    current = get_result(result_id)
    if not current or current['runtime_job_id'] != job['id'] or current['provider'] != 'github':
        raise ValueError('Promotion result linkage mismatch')
    if current['status'] in {'completed', 'failed'}:
        return {'status': current['status'], 'output': current['output'], 'error': current.get('error')}
    winner = False
    if human_authorized_resume and (current.get('promotion_state') is None or not parameters.get('production_routing')):
        raise ValueError('Human promotion resume requires an existing routed intent')
    if current.get('promotion_state') is None:
        if (current.get('output') or {}).get('promotion_intent'):
            raise ValueError('Legacy promotion intent requires review; no new dispatch')
        intent = dict(production_result_id=result_id, runtime_job_id=job['id'], source_run_id=source_run_id,
            artifact_id=artifact.get('id'), artifact_name=artifact['name'], asset_path=parameters.get('asset_path') or 'final-output.mp4',
            asset_filename=parameters.get('asset_filename') or f"task{job['task_id']}.mp4",
            workflow=PROMOTION_WORKFLOW, branch='main', provider='github',
            pre_dispatch_run_ids=sorted(monitor.snapshot_run_ids(PROMOTION_WORKFLOW, 'main')), promotion_started_at=_utc_now())
        if not ASSET_FILE_RE.fullmatch(intent['asset_filename']):
            raise ValueError('Invalid promotion filename')
        winner = claim_promotion_execution(result_id, intent)
        current = get_result(result_id)
    intent = json.loads(current.get('promotion_metadata') or '{}')
    if not intent or intent.get('production_result_id') != result_id or intent.get('runtime_job_id') != job['id']:
        raise ValueError('Missing durable promotion correlation envelope')
    if human_authorized_resume:
        expected = {
            'production_result_id': result_id,
            'runtime_job_id': job['id'],
            'source_run_id': source_run_id,
            'artifact_id': artifact.get('id'),
            'artifact_name': artifact.get('name'),
            'asset_path': parameters.get('asset_path') or 'final-output.mp4',
            'asset_filename': parameters.get('asset_filename') or f"task{job['task_id']}.mp4",
            'workflow': PROMOTION_WORKFLOW,
            'branch': 'main',
            'provider': 'github',
        }
        if any(intent.get(key) != value for key, value in expected.items()):
            raise ValueError('Human promotion resume intent does not match render artifact')
        if current['promotion_state'] == 'intent' and not intent.get('promotion_run_id') and not intent.get('recovery_required') and not intent.get('human_resume_post_claimed_at'):
            # A prior POST with no saved run ID is ambiguous.  Only a clean
            # pre-dispatch snapshot may consume this one explicit manual claim.
            try:
                # Reuse the canonical candidate semantics: a run must be both
                # absent from the pre-dispatch snapshot and created at/after
                # the durable promotion start timestamp.  A stale API page
                # can reveal historical runs after the intent was persisted;
                # those must not block the one human POST opportunity.
                monitor.discover_run(
                    workflow=intent['workflow'],
                    branch=intent['branch'],
                    pre_dispatch_run_ids=intent['pre_dispatch_run_ids'],
                    dispatch_started_at=intent['promotion_started_at'],
                    max_attempts=1,
                    poll_interval=0,
                )
            except TimeoutError:
                pass
            else:
                raise ValueError('Promotion dispatch outcome is ambiguous')
            winner = claim_human_promotion_resume(result_id, expected_intent=expected)
            current = get_result(result_id)
            intent = json.loads(current.get('promotion_metadata') or '{}')
    if winner:
        # The claim transaction is committed; fresh authorization is checked
        # immediately before POST, including changes made while finding artifacts.
        if parameters.get('production_routing') and not human_authorized_resume:
            from intelligence.content_brain import get_plan
            from orchestration.production import _authorization_or_fail
            plan_id = parameters['content_plan_id']
            plan = get_plan(plan_id)
            _authorization_or_fail(plan_id, plan)
            if plan['revision'] != parameters['content_plan_revision']:
                raise ValueError('Stale production revision')
        try:
            promoted = (promoter or promote_artifact_to_pages)(source_run_id=intent['source_run_id'], artifact_name=intent['artifact_name'],
                asset_filename=intent['asset_filename'], asset_path=intent['asset_path'], client=client, monitor=monitor,
                pre_dispatch_run_ids=intent['pre_dispatch_run_ids'], submitted_at=intent['promotion_started_at'],
                dispatch_only=True, verify_url=False)
            try:
                update_promotion_state(result_id, 'submitted', promoted)
            except ValueError:
                observed = get_result(result_id)
                bound = json.loads(observed['promotion_metadata'])
                if observed['promotion_state'] not in {'running','completed','failed'} or bound.get('promotion_run_id') != promoted.get('promotion_run_id'):
                    raise
        except Exception:
            # Keep the full immutable envelope even when POST outcome is unknown.
            latest = get_result(result_id)
            if latest['promotion_state'] not in {'completed','failed'}:
                update_promotion_state(result_id, latest['promotion_state'], {'recovery_required': True})
            raise
        current = get_result(result_id)
        intent = json.loads(current['promotion_metadata'])
    if current['promotion_state'] in {'completed','failed'}:
        run = {'id': intent['promotion_run_id'], 'status': 'completed', 'conclusion': intent['promotion_run_conclusion'], 'html_url': intent.get('promotion_run_url')}
    elif intent.get('promotion_run_id'):
        run = client.get_workflow_run(intent['promotion_run_id'])
    else:
        run = monitor.discover_run(intent['workflow'], intent['branch'], intent['pre_dispatch_run_ids'], intent['promotion_started_at'], max_attempts=1, poll_interval=0)
    evidence = {'promotion_run_id': run['id'], 'promotion_run_url': run.get('html_url'), 'promotion_run_status': run.get('status'), 'promotion_run_conclusion': run.get('conclusion')}
    state = 'running' if run.get('status') != 'completed' else ('completed' if run.get('conclusion') == 'success' else 'failed')
    latest = get_result(result_id)
    if latest['promotion_state'] not in {'completed','failed'}:
        try:
            update_promotion_state(result_id, state, evidence)
        except ValueError:
            if get_result(result_id)['promotion_state'] not in {'completed','failed'}:
                raise
    authoritative = get_result(result_id)
    state = authoritative['promotion_state']
    saved = json.loads(authoritative['promotion_metadata'])
    output = {}
    for key in evidence:
        output[key] = saved.get(key)
    output.update(asset_path=intent['asset_path'], asset_filename=intent['asset_filename'], asset_ready=False)
    if state == 'completed':
        output.update(storage_type='github_pages', asset_url=_public_url(client, intent['asset_filename']), asset_ready=True)
    return {'status': state if state in {'completed','failed'} else 'running', 'output': output,
        'error': 'Promotion workflow failed' if state == 'failed' else None}
