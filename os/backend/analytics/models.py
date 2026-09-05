from pydantic import BaseModel


class AnalyticsMetric(BaseModel):
    video_id: str
    platform: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    watch_time: int = 0
    shares: int = 0
    collected_at: str | None = None
