from analytics.manager import (
    get_latest_metrics,
    get_video_metrics,
)


def get_video_performance(video_id):
    # Preserve raw per-video snapshot history for diagnostics and charts.
    return get_video_metrics(video_id)


def get_performance_summary():
    # Summary values represent current platform state, not the sum of repeated
    # cumulative snapshots collected over time.
    metrics = get_latest_metrics()
    return {
        'total_records': len(metrics),
        'total_views': sum((x.get('views') or 0) for x in metrics)
    }
