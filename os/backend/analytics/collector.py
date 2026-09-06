from analytics.errors import AnalyticsCollectionNotReady
from analytics.registry import build_analytics_adapters
from analytics.youtube_api import YouTubeAnalyticsAPIClient
from data.platform_capabilities import get_platform_capability


class AnalyticsCollector:
    """Platform-neutral external analytics collection boundary.

    Platform capability metadata is owned by the Data Center. Provider-specific
    authorization, API calls, normalization, and persistence live behind
    registered analytics adapters. Adding a future platform should register an
    adapter instead of adding platform conditionals to this collector.

    An unavailable or unauthorized collector fails explicitly and never
    fabricates zero traffic as real analytics.
    """

    def __init__(
        self,
        youtube_client_factory=YouTubeAnalyticsAPIClient,
        *,
        adapters=None,
    ):
        self.adapters = adapters or build_analytics_adapters(
            youtube_client_factory=youtube_client_factory
        )

    def readiness(self, platform, account_id=None):
        normalized = str(platform or '').strip().lower()
        capability = get_platform_capability(normalized)

        if capability is None:
            return {
                'platform': normalized or None,
                'ready': False,
                'collector_registered': False,
                'reason': 'platform capability is not registered',
            }

        adapter = self.adapters.get(normalized)
        base = {
            'platform': normalized,
            'ready': False,
            'collector_registered': adapter is not None,
            'analytics_supported': capability['analytics_supported'],
            'metric_types': capability['metric_types'],
        }

        if not capability['analytics_supported']:
            base['reason'] = 'analytics capability is not enabled for this platform'
            return base

        if adapter is None:
            base['reason'] = 'analytics collector adapter is not registered for this platform'
            return base

        readiness = getattr(adapter, 'readiness', None)
        if not callable(readiness):
            base['reason'] = 'analytics adapter does not expose readiness()'
            return base

        base.update(readiness(account_id=account_id))
        base['platform'] = normalized
        base['analytics_supported'] = capability['analytics_supported']
        base['metric_types'] = capability['metric_types']
        return base

    def _ready_adapter(self, platform, account_id=None):
        normalized = str(platform or '').strip().lower()
        status = self.readiness(normalized, account_id=account_id)
        if not status.get('ready'):
            raise AnalyticsCollectionNotReady(
                status.get('reason') or 'analytics collection is not ready'
            )

        adapter = self.adapters.get(normalized)
        if adapter is None:
            raise AnalyticsCollectionNotReady(
                f'analytics collection adapter is not implemented for platform {normalized}'
            )
        return normalized, adapter

    def collect(self, video_id, platform, account_id=None, **kwargs):
        normalized, adapter = self._ready_adapter(platform, account_id=account_id)
        collect_video = getattr(adapter, 'collect_video', None)
        if not callable(collect_video):
            raise AnalyticsCollectionNotReady(
                f'video analytics is not implemented for platform {normalized}'
            )

        return collect_video(
            video_id,
            account_id=account_id,
            content_id=kwargs.get('content_id'),
            start_date=kwargs.get('start_date'),
            end_date=kwargs.get('end_date'),
        )

    def collect_account(self, platform, account_id=None, **kwargs):
        normalized, adapter = self._ready_adapter(platform, account_id=account_id)
        collect_account = getattr(adapter, 'collect_account', None)
        if not callable(collect_account):
            raise AnalyticsCollectionNotReady(
                f'account analytics is not implemented for platform {normalized}'
            )

        return collect_account(
            account_id=account_id,
            start_date=kwargs.get('start_date'),
            end_date=kwargs.get('end_date'),
        )
