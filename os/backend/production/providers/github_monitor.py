from __future__ import annotations

import time
from datetime import datetime, timezone


TERMINAL_STATUSES = {"completed"}
FAILURE_CONCLUSIONS = {
    "failure",
    "cancelled",
    "timed_out",
    "action_required",
    "startup_failure",
    "stale",
}


def _parse_time(value):
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class GitHubRunMonitor:
    def __init__(self, client, sleep=time.sleep):
        self.client = client
        self.sleep = sleep

    def snapshot_run_ids(self, workflow, branch):
        payload = self.client.list_workflow_runs(
            workflow=workflow,
            branch=branch,
            event="workflow_dispatch",
        )
        return {
            int(run["id"])
            for run in payload.get("workflow_runs", [])
            if run.get("id") is not None
        }

    def discover_run(
        self,
        workflow,
        branch,
        pre_dispatch_run_ids,
        dispatch_started_at,
        max_attempts=30,
        poll_interval=2,
    ):
        started = _parse_time(dispatch_started_at)
        pre_ids = {int(value) for value in pre_dispatch_run_ids}

        for _ in range(max_attempts):
            payload = self.client.list_workflow_runs(
                workflow=workflow,
                branch=branch,
                event="workflow_dispatch",
            )
            candidates = []
            for run in payload.get("workflow_runs", []):
                run_id = run.get("id")
                if run_id is None or int(run_id) in pre_ids:
                    continue
                created_at = _parse_time(run.get("created_at"))
                if started and created_at and created_at < started:
                    continue
                candidates.append(run)

            if len(candidates) == 1:
                return candidates[0]
            if len(candidates) > 1:
                raise RuntimeError(
                    "Ambiguous workflow_dispatch run discovery: multiple new runs matched "
                    f"workflow={workflow!r} branch={branch!r}."
                )
            self.sleep(poll_interval)

        raise TimeoutError(
            f"Timed out discovering workflow_dispatch run for {workflow} on {branch}"
        )

    def wait_for_terminal(self, run_id, max_attempts=720, poll_interval=10):
        last = None
        for _ in range(max_attempts):
            last = self.client.get_workflow_run(run_id)
            if last.get("status") in TERMINAL_STATUSES:
                return last
            self.sleep(poll_interval)
        raise TimeoutError(f"Timed out waiting for GitHub workflow run {run_id}")

    def discover_artifact(self, run_id, expected_name=None):
        payload = self.client.get_workflow_run_artifacts(run_id)
        artifacts = [a for a in payload.get("artifacts", []) if not a.get("expired")]
        if expected_name:
            matches = [a for a in artifacts if a.get("name") == expected_name]
            if len(matches) == 1:
                return matches[0]
            if not matches:
                raise RuntimeError(
                    f"Expected artifact {expected_name!r} was not found for run {run_id}"
                )
            raise RuntimeError(
                f"Multiple artifacts named {expected_name!r} found for run {run_id}"
            )

        if len(artifacts) == 1:
            return artifacts[0]
        if not artifacts:
            raise RuntimeError(f"No non-expired artifacts found for run {run_id}")
        raise RuntimeError(
            "Artifact discovery is ambiguous; ProductionTask.parameters.artifact_name "
            "must identify the intended artifact when a run has multiple artifacts."
        )
