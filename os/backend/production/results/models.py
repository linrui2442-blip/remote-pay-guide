from pydantic import BaseModel


class ProductionResult(BaseModel):
    id: int | None = None
    runtime_job_id: int
    provider: str
    asset_id: int | None = None
    status: str = "created"
    output: dict | None = None
    error: str | None = None
