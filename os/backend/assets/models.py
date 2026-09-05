from pydantic import BaseModel
from typing import Optional, Dict, Any


class VideoAsset(BaseModel):
    asset_id: Optional[str] = None
    video_id: str
    production_result_id: Optional[str] = None
    source_provider: str
    storage_type: str
    asset_url: Optional[str] = None
    file_path: Optional[str] = None
    status: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Legacy compatibility
    source: Optional[str] = None
    location: Optional[str] = None
