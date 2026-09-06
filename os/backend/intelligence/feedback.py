from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from intelligence.scoring import calculate_score


@dataclass
class FeedbackInsight:
    video_id: str
    performance_score: int
    successful_patterns: List[str] = field(default_factory=list)
    weak_patterns: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def _number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _row_to_metrics(row) -> Dict[str, int]:
    """Map the existing analytics_metrics SQLite row into metric fields."""
    if not isinstance(row, (list, tuple)) or len(row) < 8:
        return {}
    return {
        "views": _number(row[3]),
        "likes": _number(row[4]),
        "comments": _number(row[5]),
        "watch_time": _number(row[6]),
        "shares": _number(row[7]),
    }


def _aggregate_performance(data: Any) -> Dict[str, int]:
    """Normalize existing Data Center / Analytics performance shapes.

    Data Center currently may return raw analytics rows. This function only
    reads the existing views/likes/comments/watch_time/shares fields; it does
    not invent retention or completion-rate metrics.
    """
    metric_keys = ("views", "likes", "comments", "watch_time", "shares")

    if isinstance(data, dict):
        if "performance" in data:
            return _aggregate_performance(data.get("performance"))
        return {key: _number(data.get(key, 0)) for key in metric_keys}

    if isinstance(data, tuple):
        return _row_to_metrics(data)

    if isinstance(data, list):
        totals = {key: 0 for key in metric_keys}
        for item in data:
            metrics = _aggregate_performance(item)
            for key in metric_keys:
                totals[key] += _number(metrics.get(key, 0))
        return totals

    return {key: 0 for key in metric_keys}


def analyze_feedback(data: Any, video_id: Optional[str] = None) -> FeedbackInsight:
    """Convert Data Center performance into an optimization insight."""
    inferred_video_id = video_id
    if isinstance(data, dict):
        inferred_video_id = inferred_video_id or data.get("video_id")

    metrics = _aggregate_performance(data)
    score = calculate_score(metrics)

    successful_patterns: List[str] = []
    weak_patterns: List[str] = []
    recommendations: List[str] = []

    if metrics["views"] > 1000:
        successful_patterns.append("strong view volume")
    if metrics["likes"] > 100:
        successful_patterns.append("strong like engagement")
    if metrics["comments"] > 20:
        successful_patterns.append("strong comment engagement")
    if metrics["shares"] > 20:
        successful_patterns.append("strong share activity")
    if metrics["watch_time"] > 300:
        successful_patterns.append("strong watch time")

    if score >= 75:
        recommendations.append("produce more content around the strongest observed performance patterns")
    elif score <= 25:
        if metrics["views"] <= 1000:
            weak_patterns.append("low view volume")
        if metrics["likes"] <= 100:
            weak_patterns.append("low like engagement")
        if metrics["comments"] <= 20:
            weak_patterns.append("low comment engagement")
        if metrics["shares"] <= 20:
            weak_patterns.append("low share activity")
        if metrics["watch_time"] <= 300:
            weak_patterns.append("low watch time")
        recommendations.append("test a different topic angle or template before producing more similar content")
    else:
        recommendations.append("keep the strongest elements and test one production variable in the next iteration")

    return FeedbackInsight(
        video_id=inferred_video_id or "UNKNOWN",
        performance_score=score,
        successful_patterns=successful_patterns,
        weak_patterns=weak_patterns,
        recommendations=recommendations,
    )
