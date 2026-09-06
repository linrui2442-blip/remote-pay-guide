from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from analytics.account_manager import (
    get_account_metric_history,
    get_latest_account_metrics,
)
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
from analytics.publish_bridge import (
    PublishAnalyticsTaskNotFound,
    collect_account_publish_metrics,
    collect_publish_task_metrics,
)


router = APIRouter()
collector = AnalyticsCollector()


class AnalyticsCollectionRequest(BaseModel):
    video_id: str
    platform: str
    account_id: int
    content_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class PublishTaskAnalyticsCollectionRequest(BaseModel):
    start_date: str | None = None
    end_date: str | None = None


class AccountAnalyticsCollectionRequest(BaseModel):
    platform: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    active_limit: int = Field(default=10, ge=1, le=200)


@router.post('/analytics/metrics')
def create_metric(metric: AnalyticsMetric):
    return save_metric(metric)


@router.get('/analytics/metrics')
def metrics():
    return get_metrics()


@router.get('/analytics/metrics/current')
def current_metrics():
    return get_latest_metrics()


@router.get('/analytics/accounts/current')
def current_accounts_metrics(platform: str | None = None):
    return get_latest_account_metrics(platform=platform)


@router.get('/analytics/accounts/{account_id}/metrics')
def account_metrics(account_id: int, platform: str | None = None):
    return get_account_metric_history(account_id, platform=platform)


@router.get('/analytics/accounts/{account_id}/metrics/current')
def current_account_metrics(account_id: int, platform: str | None = None):
    return get_latest_account_metrics(account_id, platform=platform)


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


@router.post('/analytics/collector/collect/publish-task/{task_id}')
def collect_publish_task(
    task_id: int,
    request: PublishTaskAnalyticsCollectionRequest | None = None,
):
    request = request or PublishTaskAnalyticsCollectionRequest()
    try:
        return collect_publish_task_metrics(
            task_id,
            collector=collector,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except PublishAnalyticsTaskNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AnalyticsCollectionNotReady as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"publish-task analytics collection failed: {exc}",
        ) from exc


@router.post('/analytics/collector/collect/account/{account_id}')
def collect_account_analytics(
    account_id: int,
    request: AccountAnalyticsCollectionRequest | None = None,
):
    request = request or AccountAnalyticsCollectionRequest()
    try:
        return collect_account_publish_metrics(
            account_id,
            platform=request.platform,
            collector=collector,
            start_date=request.start_date,
            end_date=request.end_date,
            active_limit=request.active_limit,
        )
    except AnalyticsCollectionNotReady as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"account analytics collection failed: {exc}",
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
