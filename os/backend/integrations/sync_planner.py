from analytics.registry import get_analytics_adapter_registration
from data.platform_capabilities import get_platform_capability
from integrations.sync_registry import get_content_sync_adapter


DEFAULT_ACTIVE_LIMIT = 10


def build_account_sync_plan(
    account_id: int,
    platform: str,
    *,
    requested_limit: int = DEFAULT_ACTIVE_LIMIT,
    sync_mode: str = 'incremental',
):
    normalized = str(platform or '').strip().lower()
    content_adapter = get_content_sync_adapter(normalized)
    analytics_registration = get_analytics_adapter_registration(normalized)
    capability = get_platform_capability(normalized)

    operations = []
    content_registered = content_adapter is not None
    if content_adapter is not None:
        effective_limit = min(
            max(1, int(requested_limit or content_adapter.active_limit)),
            content_adapter.active_limit,
        )
        operations.append(
            {
                'operation': 'content_sync',
                'platform': normalized,
                'sync_mode': sync_mode,
                'max_results': effective_limit,
            }
        )
    else:
        effective_limit = max(1, int(requested_limit or DEFAULT_ACTIVE_LIMIT))

    analytics_supported = bool(capability and capability.get('analytics_supported'))
    analytics_registered = analytics_registration is not None
    if analytics_supported and analytics_registered:
        operations.append(
            {
                'operation': 'analytics_sync',
                'platform': normalized,
                'active_limit': effective_limit,
            }
        )

    return {
        'account_id': account_id,
        'platform': normalized or None,
        'content_sync_registered': content_registered,
        'analytics_supported': analytics_supported,
        'analytics_sync_registered': analytics_registered,
        'active_limit': effective_limit,
        'operations': operations,
    }
