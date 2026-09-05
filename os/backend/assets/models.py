from pydantic import BaseModel


class VideoAsset(BaseModel):
    video_id: str
    source: str
    status: str
    location: str
