from fastapi import FastAPI
from pydantic import BaseModel

from integrations.github.client import GitHubClient

app = FastAPI(title="Remote Pay Guide OS")
github_client = GitHubClient()


class WorkflowRequest(BaseModel):
    workflow: str
    branch: str = "main"


@app.get("/")
def root():
    return {
        "system": "Remote Pay Guide OS",
        "status": "running",
        "phase": "15.2",
        "modules": [
            "production",
            "publish",
            "analytics"
        ]
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/production/github/status")
def github_status():
    return {
        "provider": "github_actions",
        "status": "idle"
    }


@app.post("/production/github/run")
def github_run(request: WorkflowRequest):
    github_client.trigger_workflow(
        request.workflow,
        request.branch
    )
    return {
        "provider": "github_actions",
        "status": "started"
    }
