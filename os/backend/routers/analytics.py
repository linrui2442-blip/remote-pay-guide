from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from analytics.collector import AnalyticsCollectionNotReady, AnalyticsCollector
from analytics.manager import (
    get_content_metrics,
    get_latest_content_metrics,
    get_latest_metrics,
    get_latest_platform_metrics,
    get_latest_video_metrics,
    get_metrics,
    get_platform_metrics,
    get_video_metrics,
    save_metric,
)
from analytics.models import AnalyticsMetric


router = APIRouter()
collector = AnalyticsCollector()


class AnalyticsCollectionRequest(BaseModel):
    video_id: str
    platform: str
    account_id: int
    content_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None


@router.post('/analytics/metrics')
def create_metric(metric: AnalyticsMetric):
    return save_metric(metric)


@router.get('/analytics/metrics')
def metrics():
    return get_metrics()


@router.get('/analytics/metrics/current')
def current_metrics():
    return get_latest_metrics()


@router.get('/analytics/collector/status/{platform}')
def collector_status(platform: str, account_id: int | None = None):
    return collector.readiness(platform, account_id=account_id)


@router.post('/analytics/collector/collect')
def collect_metrics(request: AnalyticsCollectionRequest):
    try:
        return collector.collect(
            request.video_id,
            request.platform,
            account_id=request.account_id,
            content_id=request.content_id,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except AnalyticsCollectionNotReady as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"analytics collection failed: {exc}",
        ) from exc


@router.get('/analytics/metrics/video/{video_id}')
def video_metrics(video_id: str):
    return get_video_metrics(video_id)


@router.get('/analytics/metrics/video/{video_id}/current')
def current_video_metrics(video_id: str):
    return get_latest_video_metrics(video_id)


@router.get('/analytics/metrics/content/{content_id}')
def content_metrics(content_id: str):
    return get_content_metrics(content_id)


@router.get('/analytics/metrics/content/{content_id}/current')
def current_content_metrics(content_id: str):
    return get_latest_content_metrics(content_id)


@router.get('/analytics/metrics/platform/{platform}')
def platform_metrics(platform: str):
    return get_platform_metrics(platform)


@router.get('/analytics/metrics/platform/{platform}/current')
def current_platform_metrics(platform: str):
    return get_latest_platform_metrics(platform)
