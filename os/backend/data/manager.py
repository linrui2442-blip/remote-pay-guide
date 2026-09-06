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
