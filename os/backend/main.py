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
from publish.registry import platform_registry, get_adapter
from accounts.models import Account
from accounts.manager import create_account, get_accounts, get_account, update_account_status
from oauth.models import OAuthToken
from oauth.manager import create_token, get_token, update_token, delete_token
from oauth.providers.youtube import YouTubeOAuthProvider
from analytics.models import AnalyticsMetric
from analytics.manager import save_metric, get_metrics, get_video_metrics, get_platform_metrics
from analytics.collector import AnalyticsCollector

app = FastAPI(title="Remote Pay Guide OS")
github_client = GitHubClient()
youtube_adapter = YouTubeAdapter()
youtube_adapter.initialize()
youtube_oauth = YouTubeOAuthProvider()
analytics_collector = AnalyticsCollector()

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
    account_id: int | None = None


class PlatformTestRequest(BaseModel):
    video_id: str
    account_id: int | None = None


class QueueRequest(BaseModel):
    publish_task_id: int


class AccountStatusRequest(BaseModel):
    status: str


class OAuthUpdateRequest(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: str | None = None


class YouTubeCallbackRequest(BaseModel):
    code: str
    account_id: int


# existing routes remain unchanged

@app.post("/analytics/metrics")
def create_metric(metric: AnalyticsMetric):
    return save_metric(metric)


@app.get("/analytics/metrics")
def analytics_metrics():
    return get_metrics()


@app.get("/analytics/video/{video_id}")
def video_metrics(video_id: str):
    return get_video_metrics(video_id)


@app.get("/analytics/platform/{platform}")
def platform_metrics(platform: str):
    return get_platform_metrics(platform)


@app.post("/analytics/collect")
def collect_metrics(video_id: str, platform: str):
    return analytics_collector.collect(video_id, platform)
