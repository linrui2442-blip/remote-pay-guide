from dataclasses import dataclass, field
from typing import List

@dataclass
class ContentInsight:
    video_id: str
    score: int
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
