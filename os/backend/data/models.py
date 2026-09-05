from dataclasses import dataclass
from typing import Any


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
