from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


@dataclass
class ContentLifecycleView:
    video_id: str
    content_metadata: Any = None
    production: Any = None
    runtime: Any = None
    result: Any = None
    asset: Any = None
    publish: Any = None
    performance: Any = None


class IntentEvent(BaseModel):
    content_id: str
    event_type: str
    video_id: str | None = None
    session_id: str | None = None
    source: str | None = None
    event_value: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str | None = None


class ConversionRecord(BaseModel):
    content_id: str
    conversion_type: str
    video_id: str | None = None
    session_id: str | None = None
    source: str | None = None
    value: float = 1.0
    currency: str | None = None
    intent_event_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str | None = None
