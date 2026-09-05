from pydantic import BaseModel
from typing import Optional

class RuntimeJob(BaseModel):
    id: Optional[int] = None
    task_id: int
    job_type: str
    provider: str
    status: str = "created"
    input: str = "{}"
    output: Optional[str] = None
    error: Optional[str] = None
