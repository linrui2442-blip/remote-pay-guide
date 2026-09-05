from fastapi import FastAPI
from pydantic import BaseModel

from integrations.github.client import GitHubClient
from assets.models import VideoAsset
from assets.manager import create_asset, get_asset, get_assets, update_status

app = FastAPI(title="Remote Pay Guide OS")
github_client = GitHubClient()


class WorkflowRequest(BaseModel):
    workflow: str
    branch: str = "main"


@app.get("/")
def root():
    return {"system": "Remote Pay Guide OS", "status": "running", "phase": "15.3", "modules": ["production", "publish", "analytics"]}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/production/github/status")
def github_status():
    return {"provider": "github_actions", "status": "idle"}


@app.post("/production/github/run")
def github_run(request: WorkflowRequest):
    github_client.trigger_workflow(request.workflow, request.branch)
    return {"provider": "github_actions", "status": "started"}


@app.get("/assets")
def assets():
    return get_assets()


@app.get("/assets/{video_id}")
def asset(video_id: str):
    return get_asset(video_id)


@app.post("/assets")
def create_video_asset(asset: VideoAsset):
    return create_asset(asset)


@app.put("/assets/{video_id}")
def update_video_asset(video_id: str, status: str):
    update_status(video_id, status)
    return get_asset(video_id)
