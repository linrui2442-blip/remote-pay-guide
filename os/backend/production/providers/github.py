import json
import threading
from datetime import datetime, timezone

from integrations.github.client import GitHubClient
from production.providers.github_monitor import GitHubRunMonitor


WORKFLOW_INPUTS = {
    "render-short01.yml": {"task_file", "task_payload_b64", "content_id", "hook", "artifact_name"},
    "render-launch02.yml": {"publish_short04", "schedule_at"},
    "os-github-bridge-test.yml": {"mode"},
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

    def submit_job(self, job):
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
                "content_id": parameters.get("content_id"),
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

    def poll_job(self, job, production_result):
        output = dict(production_result.get("output") or {})
        run_id = output.get("github_run_id")
        if not run_id:
            return {"status": "failed", "provider": "github", "error": "missing github_run_id"}
        run = self.client.get_workflow_run(run_id)
        output.update({"github_run_id": run_id, "github_run_url": run.get("html_url") or output.get("github_run_url"), "github_run_status": run.get("status"), "github_run_conclusion": run.get("conclusion")})
        if run.get("status") != "completed":
            return {"status": "running", "provider": "github", "output": output}
        if run.get("conclusion") != "success":
            return {"status": "failed", "provider": "github", "output": output, "error": f"GitHub workflow run {run_id} concluded with {run.get('conclusion') or 'unknown'}"}
        task_payload = self._payload(job).get("parameters") or {}
        expected = task_payload.get("artifact_name")
        artifact = self.monitor.discover_artifact(run_id, expected_name=expected)
        output.update({"artifact_id": artifact.get("id"), "artifact_name": artifact.get("name"), "artifact_size": artifact.get("size_in_bytes"), "artifact_expired": artifact.get("expired")})
        promotion_intent = output.get("promotion_intent")
        if not promotion_intent and production_result.get("id"):
            from production.results.manager import get_result
            durable = get_result(production_result["id"])
            if durable and durable.get("promotion_metadata"):
                try:
                    promotion_intent = json.loads(durable["promotion_metadata"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    promotion_intent = None
        if promotion_intent and not output.get("promotion_run_id"):
            runs = self.client.list_workflow_runs("promote-video-asset.yml", "main", event="workflow_dispatch").get("workflow_runs", [])
            pre_ids = {int(v) for v in promotion_intent.get("pre_run_ids", [])}
            matches = [r for r in runs if r.get("id") is not None and int(r["id"]) not in pre_ids]
            if len(matches) != 1:
                raise RuntimeError("promotion intent exists without uniquely recoverable promotion run; review required")
            recovered = matches[0]
            output.update({"promotion_run_id": recovered["id"], "promotion_run_url": recovered.get("html_url"), "promotion_run_status": recovered.get("status"), "promotion_run_conclusion": recovered.get("conclusion"), "storage_type": "github_pages", "asset_url": promotion_intent.get("asset_url") or f"https://{self.client.owner}.github.io/{self.client.repo}/media/{promotion_intent['asset_filename']}", "asset_filename": promotion_intent["asset_filename"], "asset_ready": True})
            if recovered.get("status") == "completed" and recovered.get("conclusion") != "success":
                return {"status": "failed", "provider": "github", "output": output, "error": f"promotion workflow run {recovered['id']} concluded with {recovered.get('conclusion') or 'unknown'}"}
            return {"status": "completed", "provider": "github", "output": output}
        if not promotion_intent:
            promotion_intent = {"source_run_id": run_id, "artifact_name": artifact["name"], "asset_filename": task_payload.get("asset_filename") or f"task{job.get('task_id')}.mp4", "asset_path": task_payload.get("asset_path") or "final-output.mp4", "pre_run_ids": [int(r.get("id")) for r in self.client.list_workflow_runs("promote-video-asset.yml", "main", event="workflow_dispatch").get("workflow_runs", []) if r.get("id") is not None]}
            output["promotion_intent"] = promotion_intent
            from production.results.manager import update_result
            if production_result.get("id") is not None:
                update_result(production_result["id"], status="running", output=output, bind_asset=False)
        from assets.github_pages import promote_artifact_to_pages
        promotion = promote_artifact_to_pages(source_run_id=run_id, artifact_name=artifact["name"], asset_filename=task_payload.get("asset_filename") or f"task{job.get('task_id')}.mp4", asset_path=task_payload.get("asset_path") or "final-output.mp4", client=self.client, monitor=self.monitor, verify_url=False)
        output.update(promotion)
        return {"status": "completed", "provider": "github", "output": output}

    def run(self, job):
        return self.submit_job(job)

    def get_status(self):
        return {"provider": "github", "status": "ready"}
