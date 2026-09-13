"""Isolated P1 contracts for render-short01 automation and identity propagation."""
import os
import sys
from pathlib import Path

os.environ["OS_TESTING"] = "1"
os.environ["OS_DATABASE_PATH"] = str(Path(__file__).with_name("r45-isolated.db"))
Path(os.environ["OS_DATABASE_PATH"] ).unlink(missing_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from production.providers.github import GitHubProductionProvider


class FakeClient:
    def trigger_workflow(self, workflow, branch="main", inputs=None):
        self.call = (workflow, branch, inputs)
        return {"ok": True}

    def list_workflow_runs(self, **_):
        return {"workflow_runs": [{"id": 123, "created_at": "2099-01-01T00:00:00Z"}]}


class FakeMonitor:
    def snapshot_run_ids(self, *_): return set()
    def discover_run(self, *args, **kwargs): return {"id": 123, "status": "queued", "conclusion": None}


provider = GitHubProductionProvider(client=FakeClient())
provider.monitor = FakeMonitor()
result = provider.run({
    "input": {
        "workflow": "render-short01.yml",
        "branch": "main",
        "parameters": {
            "task_file": "tasks-short12.jsonl",
            "content_id": "short12",
            "hook": "Check the network first.",
            "artifact_name": "remote-pay-guide-short12",
            "asset_filename": "short12.mp4",
            "unknown": "must-not-send",
        },
    }
})
assert result["status"] == "submitted", result
assert result["output"]["content_id"] == "short12"
assert set(result["output"]["inputs"]) == {"task_file", "content_id", "hook", "artifact_name"}
assert "asset_filename" not in result["output"]["inputs"]
assert "unknown" not in result["output"]["inputs"]
print("P1 GitHub Line 1 automation contract passed")
