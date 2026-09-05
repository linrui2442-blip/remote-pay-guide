from pydantic import BaseModel


class ProductionTask(BaseModel):
    id: int | None = None
    task_type: str
    provider: str
    status: str = "pending"
    workflow: str
    branch: str = "main"
