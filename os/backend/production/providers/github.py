import json

from integrations.github.client import GitHubClient


WORKFLOW_INPUTS = {
    "render-launch02.yml": {"publish_short04", "schedule_at"},
}


class GitHubProductionProvider:
    def __init__(self, client=None):
        self.client = client or GitHubClient()

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

        try:
            dispatch = self.client.trigger_workflow(
                workflow=workflow,
                branch=branch,
                inputs=inputs,
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
                "workflow": workflow,
                "branch": branch,
                "inputs": inputs,
                "execution": "github_actions",
                "dispatch": dispatch,
            },
        }

    def get_status(self):
        return {"provider": "github", "status": "ready"}
