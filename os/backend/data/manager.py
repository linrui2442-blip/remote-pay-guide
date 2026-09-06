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
from data.query import query_data_center
from data.reports import get_overview_report
from data.tracking import (
    DEFAULT_ACTIVE_LIMIT,
    get_history_summaries,
    get_tracking_records,
    refresh_tracking_policy,
    set_tracking_pinned,
)


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


def refresh_account_tracking(account_id, platform, active_limit=DEFAULT_ACTIVE_LIMIT):
    return refresh_tracking_policy(account_id, platform, active_limit=active_limit)


def get_account_tracking(account_id, platform=None, state=None):
    return get_tracking_records(account_id, platform=platform, state=state)


def pin_account_content(
    account_id,
    platform,
    platform_video_id,
    pinned=True,
    active_limit=DEFAULT_ACTIVE_LIMIT,
):
    return set_tracking_pinned(
        account_id,
        platform,
        platform_video_id,
        pinned=pinned,
        active_limit=active_limit,
    )


def get_account_history(account_id, platform=None):
    return get_history_summaries(account_id, platform=platform)


def query_data_center_view(
    *,
    account_id=None,
    platform=None,
    scope="active",
    metrics=None,
    sort_by="views",
    sort_direction="desc",
    limit=100,
):
    return query_data_center(
        account_id=account_id,
        platform=platform,
        scope=scope,
        metrics=metrics,
        sort_by=sort_by,
        sort_direction=sort_direction,
        limit=limit,
    )
