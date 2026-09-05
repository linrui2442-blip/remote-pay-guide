from production.manager import get_production_tasks
from publish.manager import get_publish_tasks
from analytics.manager import get_metrics


def get_overview_report():
    return {
        'total_videos': len(get_metrics()),
        'production_completed': len([x for x in get_production_tasks() if x.get('status') == 'completed']),
        'published_count': len([x for x in get_publish_tasks() if x.get('status') == 'published']),
        'total_views': sum(x.get('views', 0) for x in get_metrics())
    }
