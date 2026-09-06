from analytics.manager import get_metrics
from data.growth import (
    get_content_funnel,
    get_conversions,
    get_funnel_summary,
    get_intent_events,
    record_conversion,
    record_intent,
)
from data.lifecycle import get_video_lifecycle
from data.platform_capabilities import (
    get_metric_types,
    get_platform_capability,
    list_platform_capabilities,
    supports_analytics,
    supports_publish,
)
from data.reports import get_overview_report


def get_video_lifecycle_data(video_id):
    return get_video_lifecycle(video_id)


def get_overview():
    return get_overview_report()


def get_statistics():
    funnel = get_funnel_summary()
    return {
        "total_metrics": len(get_metrics()),
        "intent_events": funnel["intent_events"],
        "referral_clicks": funnel["referral_clicks"],
        "conversions": funnel["conversions"],
        "conversion_value": funnel["conversion_value"],
    }


def record_intent_event(event):
    return record_intent(event)


def record_conversion_event(record):
    return record_conversion(record)


def get_content_intent(content_id):
    return get_intent_events(content_id)


def get_content_conversions(content_id):
    return get_conversions(content_id)


def get_content_funnel_data(content_id):
    return get_content_funnel(content_id)


def get_funnel_overview():
    return get_funnel_summary()


def get_platforms():
    return list_platform_capabilities()


def get_platform(platform_name):
    return get_platform_capability(platform_name)


def get_platform_runtime_capabilities(platform_name):
    return {
        "platform": (platform_name or "").strip().lower(),
        "publish_supported": supports_publish(platform_name),
        "analytics_supported": supports_analytics(platform_name),
        "metric_types": get_metric_types(platform_name),
    }
