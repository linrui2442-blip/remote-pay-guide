import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.network import configure_outbound_proxy

# Browser OAuth can succeed through a Windows proxy while Python API calls
# still go direct and time out. Configure outbound routing before external
# integrations are initialized. A saved manual OS proxy has priority.
configure_outbound_proxy()

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
    accounts,
    settings,
)

app = FastAPI(title="Remote Pay Guide OS")

frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "OS_FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(accounts.router)
app.include_router(settings.router)


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
