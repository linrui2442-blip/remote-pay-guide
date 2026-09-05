from fastapi import FastAPI
from pydantic import BaseModel

from integrations.github.client import GitHubClient
from assets.models import VideoAsset
from assets.manager import create_asset, get_asset, get_assets, update_status
from publish.models import PublishTask
from publish.manager import (
    create_publish_task,
    get_publish_tasks,
    get_publish_task,
    update_publish_status,
)
from publish.adapters.youtube import YouTubeAdapter
from publish.queue import PublishQueue
from publish.worker import PublishWorker
from publish.scheduler import PublishScheduler
from accounts.models import Account
from accounts.manager import create_account, get_accounts, get_account, update_account_status

app = FastAPI(title="Remote Pay Guide OS")
github_client = GitHubClient()
youtube_adapter = YouTubeAdapter()
youtube_adapter.initialize()

publish_queue = PublishQueue()
publish_worker = PublishWorker(publish_queue)
publish_scheduler = PublishScheduler(publish_queue)


class WorkflowRequest(BaseModel):
    workflow: str
    branch: str = "main"


class PublishStatusRequest(BaseModel):
    status: str


class YouTubeTestRequest(BaseModel):
    video_id: str


class QueueRequest(BaseModel):
    publish_task_id: int


class AccountStatusRequest(BaseModel):
    status: str


@app.get("/")
def root():
    return {"system": "Remote Pay Guide OS", "status": "running", "phase": "15.4D", "modules": ["production", "publish", "analytics"]}


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


@app.post("/publish/tasks")
def create_publish(task: PublishTask):
    return create_publish_task(task)


@app.get("/publish/tasks")
def publish_tasks():
    return get_publish_tasks()


@app.get("/publish/tasks/{task_id}")
def publish_task(task_id: int):
    return get_publish_task(task_id)


@app.put("/publish/tasks/{task_id}")
def update_publish(task_id: int, request: PublishStatusRequest):
    update_publish_status(task_id, request.status)
    return get_publish_task(task_id)


@app.get("/publish/platforms")
def publish_platforms():
    return ["youtube"]


@app.post("/publish/youtube/test")
def youtube_test(request: YouTubeTestRequest):
    return youtube_adapter.publish_video({"video_id": request.video_id}, {"platform": "youtube"})


@app.post("/publish/queue")
def add_publish_queue(request: QueueRequest):
    return {"queued": publish_queue.add_task(request.publish_task_id)}


@app.get("/publish/queue")
def publish_queue_status():
    return publish_queue.get_pending_tasks()


@app.post("/publish/worker/run")
def run_publish_worker():
    return publish_worker.run_once()


@app.get("/publish/scheduler/status")
def scheduler_status():
    return publish_scheduler.status()


@app.post("/accounts")
def add_account(account: Account):
    return create_account(account)


@app.get("/accounts")
def accounts():
    return get_accounts()


@app.get("/accounts/{account_id}")
def account(account_id: int):
    return get_account(account_id)


@app.put("/accounts/{account_id}")
def update_account(account_id: int, request: AccountStatusRequest):
    update_account_status(account_id, request.status)
    return get_account(account_id)
