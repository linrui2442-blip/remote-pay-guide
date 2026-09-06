from pydantic import BaseModel, Field


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
    # Platform-specific Analytics values live here so adding a provider metric
    # never requires a new SQLite column. Common cross-platform metrics above
    # remain first-class fields for compatibility with the current Data Center.
    metrics: dict = Field(default_factory=dict)
    collected_at: str | None = None
