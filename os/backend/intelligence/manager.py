from dataclasses import asdict

from data.growth import get_content_funnel
from data.lifecycle import get_video_lifecycle
from data.performance import get_video_performance
from intelligence.analyzer import ContentAnalyzer
from intelligence.feedback import analyze_feedback
from intelligence.insights import create_insight
from intelligence.strategy import build_production_strategy
from intelligence.task_generator import generate_production_task


analyzer = ContentAnalyzer()


def build_insight_context(video_id, lifecycle, performance, funnel=None):
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
        "metrics_snapshot": performance,
        "growth_funnel": funnel or {},
    }


def analyze_video(video_id):
    lifecycle = get_video_lifecycle(video_id)
    performance = get_video_performance(video_id)
    funnel = get_content_funnel(video_id)
    feedback = analyze_feedback(
        {
            "video_id": video_id,
            "performance": performance,
            "funnel": funnel,
        }
    )
    response = analyzer.analyze(
        lifecycle,
        {
            "platform_metrics": performance,
            "growth_funnel": funnel,
        },
    )

    context = build_insight_context(video_id, lifecycle, performance, funnel)

    insight = {
        "video_id": video_id,
        "score": feedback.performance_score,
        "strengths": feedback.successful_patterns,
        "weaknesses": feedback.weak_patterns,
        "recommendations": feedback.recommendations,
        "ai_response": response,
        **context,
    }

    return create_insight(insight)


def generate_feedback_strategy(video_id):
    """Build the next ProductionTask from the full Data Center funnel.

    This is an internal orchestration entry point only. It does not schedule
    the task, create a Runtime Job, or execute a Provider.
    """
    lifecycle = get_video_lifecycle(video_id)
    performance = get_video_performance(video_id)
    funnel = get_content_funnel(video_id)

    feedback = analyze_feedback(
        {
            "video_id": video_id,
            "performance": performance,
            "funnel": funnel,
            "lifecycle": lifecycle,
        }
    )
    strategy = build_production_strategy(feedback)
    task = generate_production_task(strategy)

    return {
        "feedback": asdict(feedback),
        "strategy": asdict(strategy),
        "production_task": asdict(task),
        "growth_funnel": funnel,
    }
