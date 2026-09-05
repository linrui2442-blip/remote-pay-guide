from dataclasses import dataclass, field
from typing import Any, Dict

@dataclass
class AIRequest:
    task_type: str
    model: str = "auto"
    prompt: str = ""
    input: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AIResponse:
    status: str
    model: str = "auto"
    output: Any = None
    usage: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
