from data.lifecycle import get_video_lifecycle
from data.reports import get_overview_report
from analytics.manager import get_metrics


def get_video_lifecycle_data(video_id):
    return get_video_lifecycle(video_id)


def get_overview():
    return get_overview_report()


def get_statistics():
    return {
        'total_metrics': len(get_metrics())
    }
