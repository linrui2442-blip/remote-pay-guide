from dataclasses import dataclass
from typing import Any, Callable

from integrations.youtube import YouTubeContentSync
from integrations.instagram import InstagramContentSync


@dataclass(frozen=True)
class ContentSyncAdapter:
    platform: str
    factory: Callable[[], Any]
    active_limit: int = 10
    supports_incremental: bool = True
    supports_full_refresh: bool = True


_CONTENT_SYNC_ADAPTERS: dict[str, ContentSyncAdapter] = {}


def _normalize_platform(platform: str | None) -> str:
    return str(platform or '').strip().lower()


def register_content_sync_adapter(
    platform: str,
    factory: Callable[[], Any],
    *,
    active_limit: int = 10,
    supports_incremental: bool = True,
    supports_full_refresh: bool = True,
    replace: bool = False,
) -> ContentSyncAdapter:
    normalized = _normalize_platform(platform)
    if not normalized:
        raise ValueError('platform is required')
    if normalized in _CONTENT_SYNC_ADAPTERS and not replace:
        raise ValueError(f'content sync adapter already registered for {normalized}')

    adapter = ContentSyncAdapter(
        platform=normalized,
        factory=factory,
        active_limit=max(1, int(active_limit or 1)),
        supports_incremental=bool(supports_incremental),
        supports_full_refresh=bool(supports_full_refresh),
    )
    _CONTENT_SYNC_ADAPTERS[normalized] = adapter
    return adapter


def get_content_sync_adapter(platform: str | None) -> ContentSyncAdapter | None:
    return _CONTENT_SYNC_ADAPTERS.get(_normalize_platform(platform))


def list_content_sync_adapters() -> list[dict[str, Any]]:
    return [
        {
            'platform': adapter.platform,
            'active_limit': adapter.active_limit,
            'supports_incremental': adapter.supports_incremental,
            'supports_full_refresh': adapter.supports_full_refresh,
        }
        for adapter in sorted(
            _CONTENT_SYNC_ADAPTERS.values(), key=lambda item: item.platform
        )
    ]


def run_content_sync(
    account_id: int,
    platform: str,
    *,
    max_results: int = 10,
    sync_mode: str = 'incremental',
):
    normalized = _normalize_platform(platform)
    adapter = get_content_sync_adapter(normalized)
    if adapter is None:
        raise RuntimeError(
            f'content sync adapter is not registered for platform {normalized or "unknown"}'
        )

    normalized_mode = str(sync_mode or 'incremental').strip().lower()
    if normalized_mode == 'incremental' and not adapter.supports_incremental:
        raise ValueError(f'incremental sync is not supported for platform {normalized}')
    if normalized_mode == 'full_refresh' and not adapter.supports_full_refresh:
        raise ValueError(f'full refresh is not supported for platform {normalized}')
    if normalized_mode not in {'incremental', 'full_refresh'}:
        raise ValueError(f'unsupported content sync mode: {sync_mode}')

    effective_results = min(
        max(1, int(max_results or adapter.active_limit)),
        adapter.active_limit,
    )
    service = adapter.factory()
    sync = getattr(service, 'sync', None)
    if not callable(sync):
        raise RuntimeError(
            f'content sync adapter for platform {normalized} does not implement sync()'
        )

    return sync(
        account_id,
        max_results=effective_results,
        sync_mode=normalized_mode,
    )


register_content_sync_adapter(
    'youtube',
    YouTubeContentSync,
    active_limit=10,
    supports_incremental=True,
    supports_full_refresh=True,
)

register_content_sync_adapter(
    'instagram',
    InstagramContentSync,
    active_limit=10,
    supports_incremental=True,
    supports_full_refresh=True,
)
