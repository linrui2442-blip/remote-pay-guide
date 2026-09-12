from typing import Literal, Optional

from pydantic import BaseModel, Field


class PublishTask(BaseModel):
    id: Optional[int] = None
    asset_id: Optional[str] = None
    video_id: Optional[str] = None  # Legacy fallback.
    platform: str
    account_id: Optional[int] = None
    status: str = "pending"
    scheduled_time: Optional[str] = None

    title: Optional[str] = None
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    privacy_status: Literal["private", "unlisted", "public"] = "private"

    platform_video_id: Optional[str] = None
    published_url: Optional[str] = None
    error_message: Optional[str] = None
    provider_operation_id: Optional[str] = None
    provider_operation_status: Optional[str] = None
    provider_operation_updated_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
