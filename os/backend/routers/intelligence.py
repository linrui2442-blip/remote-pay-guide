from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from intelligence.feedback_bridge import (
    get_content_feedback_history,
    get_latest_account_feedback,
    materialize_feedback_task,
    refresh_account_feedback,
)
from intelligence.insights import get_insights, get_video_insight
from intelligence.manager import analyze_video
from production.tasks.execution import get_execution_readiness
from intelligence.content_brain import DeterministicContentPlanProvider, save_plan, get_plan, list_plans, update_plan, set_plan_status
from intelligence.task_generator import generate_production_task
from intelligence.production_spec import build_production_spec
from intelligence.feedback_bridge import get_feedback_snapshot


router = APIRouter()


class AccountFeedbackRefreshRequest(BaseModel):
    platform: str | None = None
    limit: int = Field(default=10, ge=1, le=200)


@router.post('/intelligence/analyze/{video_id}')
def analyze(video_id: str):
    return analyze_video(video_id)


@router.get('/intelligence/insights')
def insights():
    return get_insights()


@router.get('/intelligence/video/{video_id}')
def video_insight(video_id: str):
    return get_video_insight(video_id)


@router.post('/intelligence/feedback/account/{account_id}/refresh')
def refresh_account_intelligence(
    account_id: int,
    request: AccountFeedbackRefreshRequest | None = None,
):
    request = request or AccountFeedbackRefreshRequest()
    try:
        return refresh_account_feedback(
            account_id,
            platform=request.platform,
            limit=request.limit,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/intelligence/feedback/account/{account_id}')
def account_intelligence(
    account_id: int,
    platform: str | None = None,
    limit: int = 100,
):
    return get_latest_account_feedback(
        account_id,
        platform=platform,
        limit=limit,
    )


@router.get('/intelligence/feedback/content/{content_id}')
def content_intelligence(content_id: str, limit: int = 100):
    return get_content_feedback_history(content_id, limit=limit)


@router.post('/intelligence/feedback/{snapshot_id}/materialize')
def materialize_intelligence_task(snapshot_id: int):
    try:
        result = materialize_feedback_task(snapshot_id)
        task = result.get('production_task') if isinstance(result, dict) else None
        if isinstance(task, dict):
            task['execution'] = get_execution_readiness(task)
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/intelligence/status')
def status():
    return {
        'status': 'ready',
        'data_center_feedback_bridge': True,
        'auto_execute_production': False,
        'explicit_task_materialization': True,
        'execution_readiness_exposed': True,
    }

@router.post('/intelligence/feedback/{snapshot_id}/content-plan')
def generate_content_plan(snapshot_id: int):
    snapshot = get_feedback_snapshot(snapshot_id)
    if not snapshot: raise HTTPException(status_code=404, detail='snapshot not found')
    plan = DeterministicContentPlanProvider().generate_content_plan(snapshot, {})
    return {'plan': save_plan(plan, snapshot_id), 'runtime': {'implementation_ready': True, 'runtime_ready': False}}

@router.get('/intelligence/content-plans')
def content_plans(): return list_plans()

@router.get('/intelligence/content-plans/{plan_id}')
def content_plan(plan_id: int):
    value=get_plan(plan_id)
    if not value: raise HTTPException(status_code=404, detail='plan not found')
    return value

@router.patch('/intelligence/content-plans/{plan_id}')
def edit_content_plan(plan_id: int, changes: dict): return update_plan(plan_id, changes)

@router.post('/intelligence/content-plans/{plan_id}/approve')
def approve_content_plan(plan_id: int): return set_plan_status(plan_id, 'approved')

@router.post('/intelligence/content-plans/{plan_id}/materialize')
def materialize_content_plan(plan_id: int):
    plan=get_plan(plan_id)
    if not plan or plan['status'] != 'approved': raise HTTPException(status_code=400, detail='plan must be approved first')
    payload=dict(plan['plan']); spec=build_production_spec(__import__('intelligence.content_brain',fromlist=['ContentPlan']).ContentPlan(**payload)); payload['production_spec']=spec
    payload.update({'provider_suggestion':'github','workflow':spec['workflow'],'branch':spec['branch'],'task_type':'video_batch','parameters':{'content_plan_id':plan_id,'content_plan_revision':plan.get('revision',1),'idempotency_key':f'content-plan:{plan_id}:revision:{plan.get("revision",1)}','intelligence_snapshot_id':plan.get('source_snapshot_id'),'content_id':payload.get('content_id'),'hook':payload.get('hook'),'script':payload.get('script'),'cta':payload.get('cta'),'artifact_name':spec['artifact_name'],'task_payload_b64':spec['task_payload_b64'],'workflow':spec['workflow'],'branch':spec['branch']}})
    task=generate_production_task(payload)
    readiness=get_execution_readiness(task)
    if not readiness['ready']: raise HTTPException(status_code=422, detail=readiness)
    return {'plan': set_plan_status(plan_id, 'materialized'), 'production_task': task.__dict__ if hasattr(task,'__dict__') else task, 'execution': readiness}
