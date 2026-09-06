import json
import threading
from datetime import datetime, timezone

from integrations.github.client import GitHubClient
from production.providers.github_monitor import GitHubRunMonitor


WORKFLOW_INPUTS = {
    "render-launch02.yml": {"publish_short04", "schedule_at"},
    "os-github-bridge-test.yml": set(),
    "promote-video-asset.yml": {
        "source_run_id",
        "artifact_name",
        "asset_path",
        "asset_filename",
    },
}

_DISPATCH_LOCKS = {}
_DISPATCH_LOCKS_GUARD = threading.Lock()


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dispatch_lock(workflow, branch):
    key = (workflow, branch)
    with _DISPATCH_LOCKS_GUARD:
        lock = _DISPATCH_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _DISPATCH_LOCKS[key] = lock
        return lock


class GitHubProductionProvider:
    def __init__(self, client=None):
        self.client = client or GitHubClient()
        self.monitor = GitHubRunMonitor(self.client)

    def initialize(self):
        return {"provider": "github", "status": "ready"}

    def _payload(self, job):
        raw = job.get("input") or {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
        return {}

    def run(self, job):
        payload = self._payload(job)
        workflow = payload.get("workflow") or job.get("workflow")
        branch = payload.get("branch") or job.get("branch") or "main"
        parameters = payload.get("parameters") or {}

        if not workflow:
            return {
                "status": "failed",
                "provider": "github",
                "error": "ProductionTask workflow is required for GitHub production",
            }

        workflow_name = workflow.rsplit("/", 1)[-1]
        allowed_inputs = WORKFLOW_INPUTS.get(workflow_name, set())
        inputs = {
            key: parameters[key]
            for key in allowed_inputs
            if key in parameters and parameters[key] is not None
        }
        discover_attempts = max(1, int(parameters.get("github_discover_attempts", 30)))
        discover_interval = max(1, int(parameters.get("github_discover_interval", 2)))

        try:
            with _dispatch_lock(workflow_name, branch):
                pre_run_ids = self.monitor.snapshot_run_ids(workflow_name, branch)
                submitted_at = _utc_now()
                dispatch = self.client.trigger_workflow(
                    workflow=workflow_name,
                    branch=branch,
                    inputs=inputs,
                )
                run = self.monitor.discover_run(
                    workflow=workflow_name,
                    branch=branch,
                    pre_dispatch_run_ids=pre_run_ids,
                    dispatch_started_at=submitted_at,
                    max_attempts=discover_attempts,
                    poll_interval=discover_interval,
                )
        except Exception as exc:
            return {
                "status": "failed",
                "provider": "github",
                "error": str(exc),
            }

        return {
            "status": "submitted",
            "provider": "github",
            "output": {
                "workflow": workflow_name,
                "branch": branch,
                "inputs": inputs,
                "execution": "github_actions",
                "dispatch": dispatch,
                "submitted_at": submitted_at,
                "github_run_id": run.get("id"),
                "github_run_url": run.get("html_url"),
                "github_run_status": run.get("status"),
                "github_run_conclusion": run.get("conclusion"),
            },
        }

    def get_status(self):
        return {"provider": "github", "status": "ready"}
