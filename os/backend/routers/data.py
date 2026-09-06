from fastapi import APIRouter

from data.lifecycle import get_video_lifecycle
from data.manager import (
    get_content_conversions,
    get_content_funnel_data,
    get_content_intent,
    get_funnel_overview,
    get_overview,
    get_statistics,
    record_conversion_event,
    record_intent_event,
)
from data.models import ConversionRecord, IntentEvent
from data.performance import get_performance_summary, get_video_performance


router = APIRouter()


@router.get('/data/lifecycle/{video_id}')
def lifecycle(video_id: str):
    return get_video_lifecycle(video_id)


@router.get('/data/overview')
def overview():
    return get_overview()


@router.get('/data/statistics')
def statistics():
    return get_statistics()


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
