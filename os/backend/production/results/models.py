from pydantic import BaseModel


class ProductionResult(BaseModel):
    id: int | None = None
    runtime_job_id: int
    video_id: str | None = None
    provider: str
    asset_id: str | None = None
    asset_status: str | None = None
    status: str = "created"
    output: dict | None = None
    error: str | None = None
