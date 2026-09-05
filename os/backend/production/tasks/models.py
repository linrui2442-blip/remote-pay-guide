from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ProductionTask:
    """Unified production instruction model.

    Supports both legacy task files and future AI Intelligence generated tasks.
    """

    id: Optional[int] = None
    source: str = "legacy"
    objective: str = ""
    provider: str = "github"
    template: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    resources: List[Any] = field(default_factory=list)
    priority: int = 0
    status: str = "created"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def validate(self):
        if self.source not in {"legacy", "ai_intelligence"}:
            raise ValueError("Invalid ProductionTask source")
        if self.provider not in {"github", "ai_gateway"}:
            raise ValueError("Invalid ProductionTask provider")
        return True
