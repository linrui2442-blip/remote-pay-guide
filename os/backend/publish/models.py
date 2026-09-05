from pydantic import BaseModel
from typing import Optional


class PublishTask(BaseModel):
    id: Optional[int] = None
    asset_id: Optional[str] = None
    video_id: Optional[str] = None
    platform: str
    status: str = "pending"
    scheduled_time: Optional[str] = None
