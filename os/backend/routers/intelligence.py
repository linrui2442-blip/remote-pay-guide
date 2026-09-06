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
        return materialize_feedback_task(snapshot_id)
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
    }
