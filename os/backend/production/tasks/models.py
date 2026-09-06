from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


VALID_SOURCES = {"legacy", "ai_intelligence"}
VALID_PROVIDERS = {"github", "ai_gateway"}
VALID_STATUSES = {"created", "queued", "scheduled", "running", "completed", "failed"}


@dataclass
class ProductionTask:
    """Canonical production instruction used by every Production Center entry path."""

    id: Optional[int] = None
    source: str = "legacy"
    objective: str = ""
    provider: str = "github"
    template: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    resources: List[Any] = field(default_factory=list)
    priority: int = 0
    status: str = "created"

    # Legacy Production Center compatibility fields.
    task_type: str = ""
    workflow: str = ""
    branch: str = "main"

    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def validate(self):
        if self.source not in VALID_SOURCES:
            raise ValueError("Invalid ProductionTask source")
        if self.provider not in VALID_PROVIDERS:
            raise ValueError("Invalid ProductionTask provider")
        if self.status not in VALID_STATUSES:
            raise ValueError("Invalid ProductionTask status")
        if not self.branch:
            raise ValueError("ProductionTask branch is required")
        return True
