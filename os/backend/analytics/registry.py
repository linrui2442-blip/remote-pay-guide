from dataclasses import dataclass
from typing import Any, Callable

from analytics.adapters.youtube import YouTubeAnalyticsAdapter
from analytics.youtube_api import YouTubeAnalyticsAPIClient


@dataclass(frozen=True)
class AnalyticsAdapterRegistration:
    platform: str
    factory: Callable[..., Any]


_ANALYTICS_ADAPTERS: dict[str, AnalyticsAdapterRegistration] = {}


def _normalize_platform(platform: str | None) -> str:
    return str(platform or '').strip().lower()


def register_analytics_adapter(
    platform: str,
    factory: Callable[..., Any],
    *,
    replace: bool = False,
) -> AnalyticsAdapterRegistration:
    normalized = _normalize_platform(platform)
    if not normalized:
        raise ValueError('platform is required')
    if normalized in _ANALYTICS_ADAPTERS and not replace:
        raise ValueError(f'analytics adapter already registered for {normalized}')

    registration = AnalyticsAdapterRegistration(
        platform=normalized,
        factory=factory,
    )
    _ANALYTICS_ADAPTERS[normalized] = registration
    return registration


def get_analytics_adapter_registration(
    platform: str | None,
) -> AnalyticsAdapterRegistration | None:
    return _ANALYTICS_ADAPTERS.get(_normalize_platform(platform))


def list_analytics_adapter_registrations() -> list[dict[str, str]]:
    return [
        {'platform': item.platform}
        for item in sorted(_ANALYTICS_ADAPTERS.values(), key=lambda value: value.platform)
    ]


def build_analytics_adapters(**context) -> dict[str, Any]:
    return {
        platform: registration.factory(**context)
        for platform, registration in _ANALYTICS_ADAPTERS.items()
    }


def _youtube_factory(**context):
    return YouTubeAnalyticsAdapter(
        client_factory=context.get('youtube_client_factory') or YouTubeAnalyticsAPIClient
    )


register_analytics_adapter('youtube', _youtube_factory)
