from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from data.lifecycle import get_video_lifecycle
from data.manager import (
    get_account_history,
    get_account_tracking,
    get_content_conversions,
    get_content_funnel_data,
    get_content_intent,
    get_funnel_overview,
    get_overview,
    get_platform,
    get_platform_runtime_capabilities,
    get_platforms,
    get_statistics,
    pin_account_content,
    query_data_center_view,
    record_conversion_event,
    record_intent_event,
    refresh_account_tracking,
)
from data.models import ConversionRecord, IntentEvent
from data.performance import get_performance_summary, get_video_performance


router = APIRouter()


class TrackingRefreshRequest(BaseModel):
    platform: str
    active_limit: int = Field(default=10, ge=1, le=200)


class TrackingPinRequest(BaseModel):
    platform: str
    pinned: bool = True
    active_limit: int = Field(default=10, ge=1, le=200)


@router.get('/data/lifecycle/{video_id}')
def lifecycle(video_id: str):
    return get_video_lifecycle(video_id)


@router.get('/data/overview')
def overview():
    return get_overview()


@router.get('/data/statistics')
def statistics():
    return get_statistics()


@router.get('/data/query')
def data_query(
    account_id: int | None = None,
    platform: str | None = None,
    scope: str = 'active',
    metrics: str | None = None,
    sort_by: str = 'views',
    sort_direction: str = 'desc',
    limit: int = 100,
):
    try:
        return query_data_center_view(
            account_id=account_id,
            platform=platform,
            scope=scope,
            metrics=metrics,
            sort_by=sort_by,
            sort_direction=sort_direction,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/data/performance/summary')
def performance_summary():
    return get_performance_summary()


@router.get('/data/performance/{video_id}')
def performance(video_id: str):
    return get_video_performance(video_id)


@router.post('/data/intent')
def create_intent_event(event: IntentEvent):
    return record_intent_event(event)


@router.get('/data/intent/{content_id}')
def intent_events(content_id: str):
    return get_content_intent(content_id)


@router.post('/data/conversion')
def create_conversion(record: ConversionRecord):
    return record_conversion_event(record)


@router.get('/data/conversion/{content_id}')
def conversions(content_id: str):
    return get_content_conversions(content_id)


@router.get('/data/funnel/summary')
def funnel_summary():
    return get_funnel_overview()


@router.get('/data/funnel/{content_id}')
def content_funnel(content_id: str):
    return get_content_funnel_data(content_id)


@router.get('/data/platforms')
def platforms():
    return get_platforms()


@router.get('/data/platforms/{platform_name}')
def platform_capability(platform_name: str):
    capability = get_platform(platform_name)
    if capability is None:
        raise HTTPException(status_code=404, detail='platform capability not found')
    return capability


@router.get('/data/platforms/{platform_name}/runtime')
def platform_runtime_capability(platform_name: str):
    capability = get_platform(platform_name)
    if capability is None:
        raise HTTPException(status_code=404, detail='platform capability not found')
    return get_platform_runtime_capabilities(platform_name)


@router.post('/data/tracking/account/{account_id}/refresh')
def refresh_tracking(account_id: int, request: TrackingRefreshRequest):
    try:
        return refresh_account_tracking(
            account_id,
            request.platform,
            active_limit=request.active_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/data/tracking/account/{account_id}')
def tracking_records(
    account_id: int,
    platform: str | None = None,
    state: str | None = None,
):
    try:
        return get_account_tracking(account_id, platform=platform, state=state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/data/tracking/account/{account_id}/pin/{platform_video_id}')
def pin_tracking_item(
    account_id: int,
    platform_video_id: str,
    request: TrackingPinRequest,
):
    try:
        return pin_account_content(
            account_id,
            request.platform,
            platform_video_id,
            pinned=request.pinned,
            active_limit=request.active_limit,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/data/tracking/account/{account_id}/history')
def tracking_history(account_id: int, platform: str | None = None):
    return get_account_history(account_id, platform=platform)
