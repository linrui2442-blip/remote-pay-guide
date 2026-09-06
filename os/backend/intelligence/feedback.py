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
    intent_events: int = 0
    referral_clicks: int = 0
    conversions: int = 0
    conversion_value: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def _number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _row_to_metrics(row) -> Dict[str, int]:
    """Map a legacy analytics_metrics SQLite row into metric fields."""
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
    """Normalize existing Data Center / Analytics performance shapes."""
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


def _growth_signals(data: Any):
    """Read Content -> Traffic -> Intent -> Conversion signals when available."""
    if not isinstance(data, dict):
        return {
            "intent_events": 0,
            "referral_clicks": 0,
            "conversions": 0,
            "conversion_value": 0.0,
        }

    funnel = data.get("funnel") or {}
    if not isinstance(funnel, dict):
        funnel = {}

    intent = funnel.get("intent") or {}
    conversion = funnel.get("conversion") or {}
    intent_by_type = intent.get("by_type") or {}

    return {
        "intent_events": _number(intent.get("total")),
        "referral_clicks": _number(intent_by_type.get("binance_referral_click")),
        "conversions": _number(conversion.get("total")),
        "conversion_value": _float(conversion.get("value")),
    }


def analyze_feedback(data: Any, video_id: Optional[str] = None) -> FeedbackInsight:
    """Convert Data Center performance and growth funnel data into an insight."""
    inferred_video_id = video_id
    if isinstance(data, dict):
        inferred_video_id = inferred_video_id or data.get("video_id")

    metrics = _aggregate_performance(data)
    growth = _growth_signals(data)
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

    # Business-funnel signals take priority over vanity metrics when present.
    if growth["conversions"] > 0:
        successful_patterns.append("attributed conversion observed")
        recommendations.append(
            "preserve the conversion-driving content angle and produce a controlled follow-up"
        )
    elif growth["referral_clicks"] > 0:
        successful_patterns.append("qualified referral intent observed")
        recommendations.append(
            "preserve the intent-driving message and test the conversion handoff"
        )
    elif growth["intent_events"] > 0:
        successful_patterns.append("qualified user intent observed")
        recommendations.append(
            "keep the strongest intent signals and improve the path to referral action"
        )
    elif metrics["views"] > 0:
        weak_patterns.append("traffic without qualified intent")
        recommendations.append(
            "adjust audience and problem framing to turn traffic into qualified payment intent"
        )

    if not recommendations:
        if score >= 75:
            recommendations.append(
                "produce more content around the strongest observed performance patterns"
            )
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
            recommendations.append(
                "test a different topic angle or template before producing more similar content"
            )
        else:
            recommendations.append(
                "keep the strongest elements and test one production variable in the next iteration"
            )

    return FeedbackInsight(
        video_id=inferred_video_id or "UNKNOWN",
        performance_score=score,
        successful_patterns=successful_patterns,
        weak_patterns=weak_patterns,
        recommendations=recommendations,
        intent_events=growth["intent_events"],
        referral_clicks=growth["referral_clicks"],
        conversions=growth["conversions"],
        conversion_value=growth["conversion_value"],
    )
