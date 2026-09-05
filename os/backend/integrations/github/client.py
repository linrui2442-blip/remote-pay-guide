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
            "Accept": "application/vnd.github+json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def workflow_status(self):
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/actions/runs"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def trigger_workflow(self, workflow, branch="main"):
        url = (
            f"{self.base_url}/repos/{self.owner}/{self.repo}"
            f"/actions/workflows/{workflow}/dispatches"
        )
        response = requests.post(
            url,
            headers=self.headers,
            json={"ref": branch},
            timeout=10,
        )
        response.raise_for_status()
        return {"status": "started"}
