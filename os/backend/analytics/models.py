from pydantic import BaseModel


class AnalyticsMetric(BaseModel):
    video_id: str
    platform: str
    account_id: int | None = None
    content_id: str | None = None
    source: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    impressions: int = 0
    views: int = 0
    clicks: int = 0
    ctr: float | None = None
    likes: int = 0
    comments: int = 0
    watch_time: int = 0
    average_view_duration: float | None = None
    retention: float | None = None
    shares: int = 0
    collected_at: str | None = None
