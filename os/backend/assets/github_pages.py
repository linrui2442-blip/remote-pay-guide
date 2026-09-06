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


def _verify_public_url(url, max_attempts=24, poll_interval=5):
    last_error = None
    for _ in range(max_attempts):
        try:
            response = requests.head(url, allow_redirects=True, timeout=15)
            if response.status_code < 400:
                return True
            last_error = f"HTTP {response.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(poll_interval)
    raise TimeoutError(f"GitHub Pages URL did not become reachable: {url} ({last_error})")


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
):
    client = client or GitHubClient()
    monitor = monitor or GitHubRunMonitor(client)

    if not ASSET_FILE_RE.fullmatch(asset_filename or ""):
        raise ValueError("asset_filename must be a simple unique .mp4 filename")

    pre_ids = monitor.snapshot_run_ids(PROMOTION_WORKFLOW, "main")
    submitted_at = _utc_now()
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
