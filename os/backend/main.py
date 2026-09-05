from fastapi import FastAPI
from pydantic import BaseModel
from integrations.github.client import GitHubClient
from assets.models import VideoAsset
from assets.manager import create_asset,get_asset,get_assets,update_status
from publish.models import PublishTask
from publish.manager import create_publish_task,get_publish_tasks,get_publish_task,update_publish_status
from publish.queue import PublishQueue
from publish.worker import PublishWorker
from publish.scheduler import PublishScheduler
from publish.registry import platform_registry,get_adapter
from accounts.models import Account
from accounts.manager import create_account,get_accounts,get_account,update_account_status
from oauth.models import OAuthToken
from oauth.manager import create_token,get_token,update_token,delete_token
from oauth.providers.youtube import YouTubeOAuthProvider
from analytics.models import AnalyticsMetric
from analytics.manager import save_metric,get_metrics,get_video_metrics,get_platform_metrics
from analytics.collector import AnalyticsCollector

app=FastAPI(title="Remote Pay Guide OS")
github_client=GitHubClient()
youtube_oauth=YouTubeOAuthProvider()
analytics_collector=AnalyticsCollector()
publish_queue=PublishQueue()
publish_worker=PublishWorker(publish_queue)
publish_scheduler=PublishScheduler(publish_queue)

class WorkflowRequest(BaseModel):
 workflow:str
 branch:str="main"
class PublishStatusRequest(BaseModel):
 status:str
class PlatformTestRequest(BaseModel):
 video_id:str
 account_id:int|None=None
class AccountStatusRequest(BaseModel):
 status:str
class OAuthUpdateRequest(BaseModel):
 access_token:str|None=None
 refresh_token:str|None=None
 expires_at:str|None=None
class YouTubeCallbackRequest(BaseModel):
 code:str
 account_id:int

@app.get('/health')
def health(): return {'status':'healthy'}
@app.get('/production/github/status')
def github_status(): return {'provider':'github_actions','status':'idle'}
@app.post('/production/github/run')
def github_run(request:WorkflowRequest):
 github_client.trigger_workflow(request.workflow,request.branch); return {'status':'started'}

@app.get('/assets')
def assets(): return get_assets()
@app.get('/assets/{video_id}')
def asset(video_id:str): return get_asset(video_id)
@app.post('/assets')
def create_video_asset(asset:VideoAsset): return create_asset(asset)

@app.post('/publish/tasks')
def create_publish(task:PublishTask): return create_publish_task(task)
@app.get('/publish/tasks')
def publish_tasks(): return get_publish_tasks()
@app.get('/publish/tasks/{task_id}')
def publish_task(task_id:int): return get_publish_task(task_id)
@app.put('/publish/tasks/{task_id}')
def update_publish(task_id:int,request:PublishStatusRequest): update_publish_status(task_id,request.status); return get_publish_task(task_id)
@app.get('/publish/platforms')
def publish_platforms(): return list(platform_registry.keys())
@app.post('/publish/{platform}/test')
def platform_test(platform:str,request:PlatformTestRequest):
 adapter=get_adapter(platform)
 return {'status':'unsupported_platform'} if adapter is None else adapter.publish_video({'video_id':request.video_id},request.account_id)
@app.get('/publish/queue')
def queue(): return publish_queue.get_pending_tasks()
@app.post('/publish/worker/run')
def worker(): return publish_worker.run_once()
@app.get('/publish/scheduler/status')
def scheduler(): return publish_scheduler.status()

@app.post('/accounts')
def add_account(account:Account): return create_account(account)
@app.get('/accounts')
def accounts(): return get_accounts()
@app.get('/accounts/{account_id}')
def account(account_id:int): return get_account(account_id)
@app.put('/accounts/{account_id}')
def update_account(account_id:int,request:AccountStatusRequest): update_account_status(account_id,request.status); return get_account(account_id)

@app.post('/oauth/tokens')
def add_token(token:OAuthToken): return create_token(token.model_dump())
@app.get('/oauth/tokens/{account_id}')
def oauth_token(account_id:int): return get_token(account_id)
@app.put('/oauth/tokens/{account_id}')
def edit_token(account_id:int,request:OAuthUpdateRequest): return update_token(account_id,request.model_dump())
@app.delete('/oauth/tokens/{account_id}')
def remove_token(account_id:int): return delete_token(account_id)
@app.get('/oauth/youtube/authorize')
def authorize(client_id:str,redirect_uri:str): return youtube_oauth.get_authorization_url(client_id,redirect_uri)
@app.post('/oauth/youtube/callback')
def callback(request:YouTubeCallbackRequest):
 token=youtube_oauth.exchange_code(request.code); create_token({'account_id':request.account_id,**token}); update_account_status(request.account_id,'active'); return {'status':'connected','account_id':request.account_id}

@app.post('/analytics/metrics')
def create_metric(metric:AnalyticsMetric): return save_metric(metric)
@app.get('/analytics/metrics')
def analytics_metrics(): return get_metrics()
@app.get('/analytics/video/{video_id}')
def video_metrics(video_id:str): return get_video_metrics(video_id)
@app.get('/analytics/platform/{platform}')
def platform_metrics(platform:str): return get_platform_metrics(platform)
@app.post('/analytics/collect')
def collect(video_id:str,platform:str): return analytics_collector.collect(video_id,platform)
