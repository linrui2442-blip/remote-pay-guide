import os
from fastapi import APIRouter, HTTPException
from ai.providers.text import TextProviderError
from pydantic import BaseModel, Field, Extra
from typing import Literal

from intelligence.feedback_bridge import (
    get_content_feedback_history,
    get_latest_account_feedback,
    materialize_feedback_task,
    refresh_account_feedback,
)
from intelligence.insights import get_insights, get_video_insight
from intelligence.manager import analyze_video
from production.tasks.execution import get_execution_readiness
from intelligence.content_brain import LLMContentPlanProvider, select_content_plan_provider, save_plan, get_plan, list_plans, update_plan, set_plan_status
from intelligence.task_generator import generate_production_task
from intelligence.production_spec import build_production_spec
from intelligence.novelty import evaluate_content_plan_novelty
from intelligence.content_plan_service import approve_plan, materialize_plan
from intelligence.feedback_bridge import get_feedback_snapshot
from intelligence.policy import evaluate_policy, get_current_policy_decision, list_policy_history, list_review_queue
from intelligence.autonomy import get_effective_authorization, set_policy_override, clear_policy_override


router = APIRouter()


class AccountFeedbackRefreshRequest(BaseModel):
    platform: str | None = None
    limit: int = Field(default=10, ge=1, le=200)


class ContentPlanGenerationRequest(BaseModel):
    human_brief: str | None = None
    human_constraints: dict | None = None

class OverridePolicyRequest(BaseModel):
    override_decision: Literal['AUTO','REVIEW','BLOCK']
    reason: str = Field(min_length=1, max_length=500)
    class Config: extra = Extra.forbid

class ClearPolicyOverrideRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    class Config: extra = Extra.forbid


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
def generate_content_plan(snapshot_id: int, request: ContentPlanGenerationRequest | None = None):
    snapshot = get_feedback_snapshot(snapshot_id)
    if not snapshot: raise HTTPException(status_code=404, detail='snapshot not found')
    context = {}
    if request:
        context = {'human_brief': request.human_brief or '', 'human_constraints': request.human_constraints or {}}
    provider = select_content_plan_provider()
    runtime = provider.readiness() if hasattr(provider, 'readiness') else {'implementation_ready': True, 'runtime_ready': True}
    if not runtime.get('runtime_ready') and os.getenv('OS_CONTENT_PLAN_PROVIDER', 'deterministic').lower() == 'llm':
        raise HTTPException(status_code=503, detail={'error': 'provider not configured', 'runtime_ready': False, 'missing_configuration': runtime.get('missing_configuration', [])})
    try:
        plan = provider.generate_content_plan(snapshot, context)
    except TextProviderError as exc:
        message = str(exc)
        status = 504 if 'timeout' in message else 502
        raise HTTPException(status_code=status, detail='external text provider failure') from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {'plan': save_plan(plan, snapshot_id), 'runtime': {**runtime, 'real_ai': isinstance(provider, LLMContentPlanProvider)}}

@router.get('/intelligence/content-plans')
def content_plans(): return list_plans()

@router.get('/intelligence/content-plans/policy/review-queue')
def policy_review_queue(): return {'items': list_review_queue()}

@router.get('/intelligence/content-plans/{plan_id}')
def content_plan(plan_id: int):
    value=get_plan(plan_id)
    if not value: raise HTTPException(status_code=404, detail='plan not found')
    return value

@router.post('/intelligence/content-plans/{plan_id}/policy/evaluate')
def evaluate_content_plan_policy(plan_id: int):
    try: return evaluate_policy(plan_id)
    except KeyError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.get('/intelligence/content-plans/{plan_id}/policy')
def content_plan_policy(plan_id: int):
    try:
        p=get_plan(plan_id)
        if not p: raise KeyError('plan not found')
        current=get_current_policy_decision(plan_id)
        return {'plan_id':plan_id,'current_revision':p['revision'],'current_decision':current,'policy_status': 'UNEVALUATED' if not list_policy_history(plan_id) else ('STALE_REVIEW_REQUIRED' if current is None else current['decision'])}
    except KeyError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.get('/intelligence/content-plans/{plan_id}/policy/effective')
def content_plan_policy_effective(plan_id: int):
    try: return get_effective_authorization(plan_id)
    except KeyError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.post('/intelligence/content-plans/{plan_id}/policy/override')
def override_content_plan_policy(plan_id: int, request: OverridePolicyRequest):
    try: return set_policy_override(plan_id, request.override_decision, request.reason)
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.post('/intelligence/content-plans/{plan_id}/policy/override/clear')
def clear_content_plan_policy_override(plan_id: int, request: ClearPolicyOverrideRequest):
    try: return clear_policy_override(plan_id, request.reason)
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.patch('/intelligence/content-plans/{plan_id}')
def edit_content_plan(plan_id: int, changes: dict): return update_plan(plan_id, changes)

@router.post('/intelligence/content-plans/{plan_id}/approve')
def approve_content_plan(plan_id: int):
    try: return approve_plan(plan_id)
    except KeyError as e: raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e: raise HTTPException(status_code=422, detail=str(e))

@router.post('/intelligence/content-plans/{plan_id}/materialize')
def materialize_content_plan(plan_id: int):
    try:
        task=materialize_plan(plan_id); return {'production_task': task.__dict__ if hasattr(task,'__dict__') else task, 'execution': get_execution_readiness(task)}
    except KeyError as e: raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e: raise HTTPException(status_code=409, detail=str(e))
