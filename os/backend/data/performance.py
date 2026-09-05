from analytics.manager import get_metrics, get_video_metrics


def get_video_performance(video_id):
    return get_video_metrics(video_id)


def get_performance_summary():
    metrics = get_metrics()
    return {
        'total_records': len(metrics),
        'total_views': sum(x.get('views', 0) for x in metrics)
    }
