import os

import requests


class GitHubClient:
    def __init__(self, owner="linrui2442-blip", repo="remote-pay-guide"):
        self.owner = owner
        self.repo = repo
        self.token = os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"

    @property
    def headers(self):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def workflow_status(self):
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/actions/runs"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def list_workflow_runs(self, workflow, branch=None, event=None, per_page=30):
        url = (
            f"{self.base_url}/repos/{self.owner}/{self.repo}"
            f"/actions/workflows/{workflow}/runs"
        )
        params = {"per_page": per_page}
        if branch:
            params["branch"] = branch
        if event:
            params["event"] = event
        response = requests.get(url, headers=self.headers, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_workflow_run(self, run_id):
        url = (
            f"{self.base_url}/repos/{self.owner}/{self.repo}"
            f"/actions/runs/{run_id}"
        )
        response = requests.get(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def get_workflow_run_artifacts(self, run_id, per_page=100):
        url = (
            f"{self.base_url}/repos/{self.owner}/{self.repo}"
            f"/actions/runs/{run_id}/artifacts"
        )
        response = requests.get(
            url,
            headers=self.headers,
            params={"per_page": per_page},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def trigger_workflow(self, workflow, branch="main", inputs=None):
        url = (
            f"{self.base_url}/repos/{self.owner}/{self.repo}"
            f"/actions/workflows/{workflow}/dispatches"
        )
        payload = {"ref": branch}
        if inputs:
            payload["inputs"] = inputs

        response = requests.post(
            url,
            headers=self.headers,
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        return {
            "status": "started",
            "workflow": workflow,
            "branch": branch,
            "inputs": inputs or {},
        }
