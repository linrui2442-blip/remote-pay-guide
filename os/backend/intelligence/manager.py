from dataclasses import asdict

from intelligence.scoring import calculate_score
from intelligence.analyzer import ContentAnalyzer
from intelligence.insights import create_insight
from intelligence.feedback import analyze_feedback
from intelligence.strategy import build_production_strategy
from intelligence.task_generator import generate_production_task
from data.lifecycle import get_video_lifecycle
from data.performance import get_video_performance

analyzer = ContentAnalyzer()


def build_insight_context(video_id, lifecycle, performance):
    production = lifecycle.get("production", {}) if isinstance(lifecycle, dict) else {}
    runtime = lifecycle.get("runtime", {}) if isinstance(lifecycle, dict) else {}
    result = lifecycle.get("result", {}) if isinstance(lifecycle, dict) else {}
    publish = lifecycle.get("publish", {}) if isinstance(lifecycle, dict) else {}

    return {
        "content_type": "video",
        "platform": publish.get("platform"),
        "provider": runtime.get("provider") or production.get("provider"),
        "production_source": result.get("provider") or production.get("provider"),
        "prompt_version": production.get("prompt_version"),
        "metrics_snapshot": performance if isinstance(performance, dict) else {},
    }


def analyze_video(video_id):
    lifecycle = get_video_lifecycle(video_id)
    performance = get_video_performance(video_id)
    score = calculate_score(performance if isinstance(performance, dict) else {})
    response = analyzer.analyze(lifecycle, performance)

    context = build_insight_context(video_id, lifecycle, performance)

    insight = {
        "video_id": video_id,
        "score": score,
        "strengths": [],
        "weaknesses": [],
        "recommendations": [],
        "ai_response": response,
        **context,
    }

    return create_insight(insight)


def generate_feedback_strategy(video_id):
    """Build the next ProductionTask from Data Center feedback.

    This is an internal orchestration entry point only. It does not schedule
    the task, create a Runtime Job, or execute a Provider.
    """
    lifecycle = get_video_lifecycle(video_id)
    performance = get_video_performance(video_id)

    feedback = analyze_feedback(
        {
            "video_id": video_id,
            "performance": performance,
            "lifecycle": lifecycle,
        }
    )
    strategy = build_production_strategy(feedback)
    task = generate_production_task(strategy)

    return {
        "feedback": asdict(feedback),
        "strategy": asdict(strategy),
        "production_task": asdict(task),
    }
