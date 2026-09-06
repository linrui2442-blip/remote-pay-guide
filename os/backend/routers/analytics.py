from fastapi import APIRouter

from analytics.manager import (
    get_content_metrics,
    get_metrics,
    get_platform_metrics,
    get_video_metrics,
    save_metric,
)
from analytics.models import AnalyticsMetric


router = APIRouter()


@router.post('/analytics/metrics')
def create_metric(metric: AnalyticsMetric):
    return save_metric(metric)


@router.get('/analytics/metrics')
def metrics():
    return get_metrics()


@router.get('/analytics/metrics/video/{video_id}')
def video_metrics(video_id: str):
    return get_video_metrics(video_id)


@router.get('/analytics/metrics/content/{content_id}')
def content_metrics(content_id: str):
    return get_content_metrics(content_id)


@router.get('/analytics/metrics/platform/{platform}')
def platform_metrics(platform: str):
    return get_platform_metrics(platform)
