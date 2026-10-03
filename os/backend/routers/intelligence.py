import os
from fastapi import APIRouter, HTTPException
from ai.providers.text import TextProviderError
from pydantic import BaseModel, Field, Extra, StrictBool
from typing import Literal
from uuid import UUID
from datetime import date

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
from intelligence.feedback_bridge import (get_feedback_snapshot, record_directed_generation_intent,
    record_directed_generation_observation, get_directed_request_status,
    GENERATION_OBSERVATION_STAGES, GENERATION_OBSERVATION_FAILURE_CODES)
from intelligence.policy import evaluate_policy, get_current_policy_decision, list_policy_history, list_review_queue
from intelligence.autonomy import get_effective_authorization, set_policy_override, clear_policy_override
from intelligence.learning import prepare_feedback_snapshot
from intelligence.content_brain import directed_creation_identity, get_directed_replay, validate_human_directive_safety


router = APIRouter()


class AccountFeedbackRefreshRequest(BaseModel):
    platform: str | None = None
    limit: int = Field(default=10, ge=1, le=200)


class ContentPlanGenerationRequest(BaseModel):
    human_brief: str | None = None
    # must_include entries are required phrases in generated content, not semantic concepts.
    human_constraints: dict | None = None
    request_id: UUID | None = None
    duplicate_risk_ack: StrictBool = False
    class Config: extra = Extra.forbid


class StrictSnapshotRequest(BaseModel):
    account_id: int = Field(gt=0)
    platform: Literal['youtube', 'instagram', 'facebook']
    start_date: date
    end_date: date
    class Config: extra = Extra.forbid


@router.post('/intelligence/feedback/prepare')
def prepare_strict_snapshot(request: StrictSnapshotRequest):
    try:
        return {'snapshot': prepare_feedback_snapshot(request.account_id, request.platform,
            request.start_date.isoformat(), request.end_date.isoformat())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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
    directed = bool(context.get('human_brief', '').strip() or context.get('human_constraints'))
    identity = fingerprint = None
    if directed:
        if not request.request_id:
            raise HTTPException(status_code=422, detail='DIRECTED_REQUEST_ID_REQUIRED')
        evidence = (snapshot.get('metrics_snapshot') or {}).get('learning_evidence') or {}
        if not evidence.get('fingerprint') or not evidence.get('window'):
            raise HTTPException(status_code=422, detail='STRICT_SNAPSHOT_REQUIRED')
        try:
            validate_human_directive_safety(context['human_brief'], context['human_constraints'])
            identity, fingerprint = directed_creation_identity(request.request_id, snapshot_id,
                context['human_brief'], context['human_constraints'])
            replay = get_directed_replay(identity, fingerprint)
        except ValueError as exc:
            raise HTTPException(status_code=409 if str(exc) == 'DIRECTED_REPLAY_CONFLICT' else 422, detail=str(exc)) from exc
        if replay:
            return _plan_with_policy(replay, {'replayed': True, 'real_ai': replay['plan'].get('generation_provider') == 'llm'})
        context['content_id'] = identity
    provider = select_content_plan_provider()
    if directed and not getattr(provider, 'supports_directed', False):
        raise HTTPException(status_code=503, detail='DIRECTED_PROVIDER_NOT_READY')
    runtime = provider.readiness() if hasattr(provider, 'readiness') else {'implementation_ready': True, 'runtime_ready': True}
    if not runtime.get('runtime_ready') and os.getenv('OS_CONTENT_PLAN_PROVIDER', 'deterministic').lower() == 'llm':
        raise HTTPException(status_code=503, detail={'error': 'provider not configured', 'runtime_ready': False, 'missing_configuration': runtime.get('missing_configuration', [])})
    if directed:
        try:
            if request.duplicate_risk_ack:
                record_directed_generation_intent(snapshot_id, identity, fingerprint, duplicate_risk_ack=True)
            else:
                record_directed_generation_intent(snapshot_id, identity, fingerprint)
        except ValueError as exc:
            replay = get_directed_replay(identity, fingerprint)
            if replay:
                return _plan_with_policy(replay, {'replayed': True})
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        plan = provider.generate_content_plan(snapshot, context)
    except TextProviderError as exc:
        message = str(exc)
        status = 504 if 'timeout' in message else 502
        raise HTTPException(status_code=status, detail='external text provider failure') from exc
    except ValueError as exc:
        if directed:
            returned = bool(getattr(exc, 'forensic_provider_returned', False))
            stage = getattr(exc, 'forensic_stage', 'PROVIDER_RETURNED')
            code = getattr(exc, 'forensic_code', 'DIRECTED_GENERATION_UNKNOWN_VALIDATION_ERROR')
            if not returned:
                stage = 'PROVIDER_OUTCOME_UNCONFIRMED'
            elif stage not in GENERATION_OBSERVATION_STAGES:
                stage = 'PROVIDER_RETURNED'
            if code not in GENERATION_OBSERVATION_FAILURE_CODES:
                code = 'DIRECTED_GENERATION_UNKNOWN_VALIDATION_ERROR'
            if returned:
                try:
                    record_directed_generation_observation(snapshot_id, identity, stage=stage,
                        failure_code=code, provider_returned=True,
                        failed_requirement_index=getattr(exc, 'forensic_requirement_index', None))
                except Exception:
                    # A failed forensic write must never mask the generation failure.
                    pass
            raise HTTPException(status_code=422, detail={'code': code, 'stage': stage}) from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if directed:
        plan.content_id = identity
        plan.source_snapshot_id = snapshot_id
        plan.source_content_id = snapshot['content_id']
        plan.generation_evidence['request_fingerprint'] = fingerprint
    if directed and isinstance(provider, LLMContentPlanProvider):
        try:
            record_directed_generation_observation(snapshot_id, identity, stage='CONTENT_PLAN_VALIDATED',
                provider_returned=True)
        except Exception as exc:
            raise HTTPException(status_code=503, detail='DIRECTED_GENERATION_OBSERVATION_UNAVAILABLE') from exc
    try:
        saved = save_plan(plan, snapshot_id, directed_request=directed)
    except ValueError:
        if directed and isinstance(provider, LLMContentPlanProvider):
            try:
                record_directed_generation_observation(snapshot_id, identity,
                    stage='CONTENT_PLAN_VALIDATED',
                    failure_code='DIRECTED_GENERATION_UNKNOWN_VALIDATION_ERROR')
            except Exception:
                pass
        raise
    if directed and isinstance(provider, LLMContentPlanProvider):
        try:
            record_directed_generation_observation(snapshot_id, identity, stage='CONTENT_PLAN_PERSISTED')
        except Exception as exc:
            raise HTTPException(status_code=503, detail='DIRECTED_GENERATION_OBSERVATION_UNAVAILABLE') from exc
    return _plan_with_policy(saved, {**runtime, 'real_ai': isinstance(provider, LLMContentPlanProvider)})


@router.get('/intelligence/feedback/{snapshot_id}/directed-request/{request_id}/status')
def directed_request_status(snapshot_id: int, request_id: UUID):
    """Only effective state; never expose stored evidence, actor, or intent JSON."""
    identity, _ = directed_creation_identity(request_id, snapshot_id, '', {})
    try:
        status = get_directed_request_status(snapshot_id, identity)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {'request_id': str(request_id),
            'effective_state': status['effective_state'],
            'can_create_new_request': status['can_create_new_request'] and not status.get('state_conflict'),
            'requires_duplicate_risk_ack': status['requires_duplicate_risk_ack']}


def _plan_with_policy(saved, runtime):
    # Persistence precedes policy; an error must not ask the caller to regenerate.
    try:
        decision = evaluate_policy(saved['id'])
        return {'plan': get_plan(saved['id']), 'runtime': runtime, 'policy': decision,
                'effective': get_effective_authorization(saved['id'])}
    except Exception:
        return {'plan': get_plan(saved['id']), 'runtime': runtime, 'policy': None,
                'effective': None, 'policy_error': 'POLICY_EVALUATION_REQUIRED'}

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
