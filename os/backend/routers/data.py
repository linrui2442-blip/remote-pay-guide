from fastapi import APIRouter

from data.lifecycle import get_video_lifecycle
from data.manager import get_overview, get_statistics
from data.performance import get_video_performance, get_performance_summary

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

@router.get('/data/performance/{video_id}')
def performance(video_id: str):
    return get_video_performance(video_id)

@router.get('/data/performance/summary')
def performance_summary():
    return get_performance_summary()
