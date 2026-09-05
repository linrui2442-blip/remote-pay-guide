from pydantic import BaseModel
from typing import Optional


class PublishTask(BaseModel):
    id: Optional[int] = None
    video_id: str
    platform: str
    status: str = "pending"
    scheduled_time: Optional[str] = None
