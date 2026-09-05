from fastapi import FastAPI
from pydantic import BaseModel

from integrations.github.client import GitHubClient

from routers import (
    production,
    runtime,
    results,
    data,
    ai,
    intelligence,
    publish,
    analytics,
    assets,
    oauth,
)

app = FastAPI(title="Remote Pay Guide OS")

app.include_router(production.router)
app.include_router(runtime.router)
app.include_router(results.router)
app.include_router(data.router)
app.include_router(ai.router)
app.include_router(intelligence.router)
app.include_router(publish.router)
app.include_router(analytics.router)
app.include_router(assets.router)
app.include_router(oauth.router)


class WorkflowRequest(BaseModel):
    workflow: str
    branch: str = "main"


github_client = GitHubClient()


@app.get('/')
def root():
    return {'system': 'Remote Pay Guide OS', 'status': 'running'}


@app.get('/health')
def health():
    return {'status': 'healthy'}


@app.get('/production/github/status')
def github_status():
    return {'provider': 'github_actions', 'status': 'idle'}


@app.post('/production/github/run')
def github_run(request: WorkflowRequest):
    github_client.trigger_workflow(request.workflow, request.branch)
    return {'status': 'started'}
