from datetime import datetime, timezone

from analytics.account_manager import save_account_metric
from analytics.errors import AnalyticsCollectionNotReady
from analytics.manager import save_metric
from analytics.models import AccountAnalyticsMetric, AnalyticsMetric
from analytics.youtube_api import YouTubeAnalyticsAPIClient
from oauth.manager import get_token, update_token
from oauth.providers.youtube import (
    YOUTUBE_ANALYTICS_SCOPE,
    YOUTUBE_READ_SCOPE,
    YOUTUBE_UPLOAD_SCOPE,
    YouTubeOAuthProvider,
)


class YouTubeAnalyticsAdapter:
    platform = 'youtube'

    def __init__(self, client_factory=YouTubeAnalyticsAPIClient):
        self.client_factory = client_factory

    def readiness(self, account_id=None):
        required_scopes = {YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE}
        legacy_scope_assumption = False
        oauth_provider = YouTubeOAuthProvider(scope_profile='analytics')
        oauth_client_configured = bool(
            oauth_provider.client_id and oauth_provider.client_secret
        )
        access_token_found = False
        refresh_token_found = False
        token_expired = None
        token_near_expiry = None

        if account_id is None:
            configured_scopes = {YOUTUBE_UPLOAD_SCOPE}
            credential_source = 'default_publish_profile'
            credential_found = None
        else:
            token = get_token(account_id)
            credential_found = bool(token)
            if token:
                access_token_found = bool(token.get('access_token'))
                refresh_token_found = bool(token.get('refresh_token'))
                expiry = oauth_provider._parse_expiry(token.get('expires_at'))
                if expiry is not None:
                    seconds_remaining = (
                        expiry - datetime.now(timezone.utc)
                    ).total_seconds()
                    token_expired = seconds_remaining <= 0
                    token_near_expiry = 0 < seconds_remaining <= 60
                configured_scopes = set(token.get('scopes') or [])
                if not configured_scopes:
                    configured_scopes = {YOUTUBE_UPLOAD_SCOPE}
                    legacy_scope_assumption = True
                credential_source = 'stored_oauth_token'
            else:
                configured_scopes = set()
                credential_source = 'stored_oauth_token'

        missing_scopes = sorted(required_scopes - configured_scopes)
        refresh_required = bool(
            account_id is not None
            and credential_found
            and (
                not access_token_found
                or token_expired is True
                or token_near_expiry is True
                or (token.get('expires_at') is None and refresh_token_found)
            )
        )
        refresh_ready = bool(refresh_token_found and oauth_client_configured)
        credential_ready = bool(
            account_id is not None
            and credential_found
            and access_token_found
            and not missing_scopes
            and oauth_client_configured
            and (not refresh_required or refresh_ready)
        )
        ready = credential_ready

        if account_id is None:
            reason = 'account_id is required to evaluate a stored YouTube analytics credential.'
        elif not credential_found:
            reason = 'YouTube OAuth credential was not found for this account.'
        elif missing_scopes:
            reason = 'YouTube OAuth credential does not include analytics read scopes.'
        elif not oauth_client_configured:
            reason = 'YouTube OAuth client configuration is unavailable in the backend runtime.'
        elif not access_token_found:
            reason = 'YouTube OAuth access token is unavailable.'
        elif refresh_required and not refresh_ready:
            reason = 'YouTube OAuth token refresh is required but unavailable.'
        else:
            reason = None

        return {
            'ready': ready,
            'credential_ready': credential_ready,
            'collector_registered': True,
            'collector_enabled': True,
            'credential_mode': 'oauth',
            'credential_source': credential_source,
            'credential_found': credential_found,
            'access_token_found': access_token_found,
            'refresh_token_found': refresh_token_found,
            'oauth_client_configured': oauth_client_configured,
            'token_expired': token_expired,
            'token_near_expiry': token_near_expiry,
            'refresh_required': refresh_required,
            'refresh_ready': refresh_ready,
            'configured_scopes': sorted(configured_scopes),
            'required_scopes': sorted(required_scopes),
            'missing_scopes': missing_scopes,
            'requires_reauthorization': bool(
                account_id is not None and credential_found and missing_scopes
            ),
            'legacy_scope_assumption': legacy_scope_assumption,
            'reason': reason,
        }

    def _client(self, account_id):
        token = get_token(account_id)
        if not token:
            raise AnalyticsCollectionNotReady(
                f'YouTube OAuth credential not found for account_id {account_id}'
            )

        oauth_provider = YouTubeOAuthProvider(scope_profile='analytics')
        valid_token, refreshed = oauth_provider.ensure_valid_token(token)
        if refreshed:
            update_token(
                account_id,
                {
                    'provider': 'youtube',
                    **valid_token,
                },
            )

        credentials = oauth_provider.build_google_credentials(valid_token)
        client = self.client_factory()
        client.initialize(credentials)
        return client

    def collect_video(
        self,
        video_id,
        *,
        account_id,
        content_id=None,
        start_date=None,
        end_date=None,
    ):
        client = self._client(account_id)
        result = client.collect_video_metrics(
            video_id,
            start_date=start_date,
            end_date=end_date,
        )
        metric = AnalyticsMetric(
            video_id=video_id,
            content_id=content_id or video_id,
            platform=self.platform,
            account_id=account_id,
            source='youtube_analytics_api',
            period_start=result.get('start_date'),
            period_end=result.get('end_date'),
            views=result.get('views', 0),
            watch_time=result.get('watch_time', 0),
            average_view_duration=result.get('average_view_duration'),
            retention=result.get('retention'),
            likes=result.get('likes', 0),
            comments=result.get('comments', 0),
            shares=result.get('shares', 0),
        )
        return save_metric(metric)

    def collect_account(
        self,
        *,
        account_id,
        start_date=None,
        end_date=None,
    ):
        client = self._client(account_id)
        result = client.collect_channel_metrics(
            start_date=start_date,
            end_date=end_date,
        )
        metrics = {
            key: value
            for key, value in result.items()
            if key not in {'start_date', 'end_date'}
        }
        metrics['average_view_percentage'] = metrics.get('retention')
        return save_account_metric(
            AccountAnalyticsMetric(
                platform=self.platform,
                account_id=account_id,
                source='youtube_analytics_api',
                period_start=result.get('start_date'),
                period_end=result.get('end_date'),
                metrics=metrics,
            )
        )
