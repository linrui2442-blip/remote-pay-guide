from analytics.manager import get_metrics
from data.content_registry import get_contents
from data.growth import get_funnel_summary
from production.manager import get_production_tasks
from publish.manager import get_publish_tasks


def get_overview_report():
    metrics = get_metrics()
    contents = get_contents()
    funnel = get_funnel_summary()

    return {
        "total_videos": len(contents),
        "production_completed": len(
            [x for x in get_production_tasks() if x.get("status") == "completed"]
        ),
        "published_count": len(
            [x for x in get_publish_tasks() if x.get("status") == "published"]
        ),
        "traffic_records": len(metrics),
        "impressions": funnel["impressions"],
        "total_views": funnel["views"],
        "clicks": funnel["clicks"],
        "intent_events": funnel["intent_events"],
        "referral_clicks": funnel["referral_clicks"],
        "conversions": funnel["conversions"],
        "conversion_value": funnel["conversion_value"],
    }
