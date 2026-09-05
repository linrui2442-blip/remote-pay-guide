from intelligence.scoring import calculate_score
from intelligence.analyzer import ContentAnalyzer
from intelligence.insights import create_insight
from data.lifecycle import get_video_lifecycle
from data.performance import get_video_performance

analyzer = ContentAnalyzer()


def analyze_video(video_id):
    lifecycle = get_video_lifecycle(video_id)
    performance = get_video_performance(video_id)
    score = calculate_score(performance if isinstance(performance, dict) else {})
    response = analyzer.analyze(lifecycle, performance)

    insight = {
        "video_id": video_id,
        "score": score,
        "strengths": [],
        "weaknesses": [],
        "recommendations": [],
        "ai_response": response
    }
    return create_insight(insight)
