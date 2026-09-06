from analytics.manager import save_metric
from analytics.models import AnalyticsMetric
from analytics.youtube_api import YouTubeAnalyticsAPIClient
from data.platform_capabilities import get_platform_capability
from oauth.manager import get_token, update_token
from oauth.providers.youtube import (
    YOUTUBE_ANALYTICS_SCOPE,
    YOUTUBE_READ_SCOPE,
    YOUTUBE_UPLOAD_SCOPE,
    YouTubeOAuthProvider,
)


class AnalyticsCollectionNotReady(RuntimeError):
    pass


def _youtube_readiness(account_id=None):
    required_scopes = {YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE}
    legacy_scope_assumption = False

    if account_id is None:
        configured_scopes = {YOUTUBE_UPLOAD_SCOPE}
        credential_source = "default_publish_profile"
        credential_found = None
    else:
        token = get_token(account_id)
        credential_found = bool(token)
        if token:
            configured_scopes = set(token.get("scopes") or [])
            if not configured_scopes:
                # Tokens created before scope persistence were produced by the
                # upload-only flow, so keep that legacy behavior explicit.
                configured_scopes = {YOUTUBE_UPLOAD_SCOPE}
                legacy_scope_assumption = True
            credential_source = "stored_oauth_token"
        else:
            configured_scopes = set()
            credential_source = "stored_oauth_token"

    missing_scopes = sorted(required_scopes - configured_scopes)
    credential_ready = not missing_scopes
    collector_enabled = True
    ready = bool(account_id is not None and credential_found and credential_ready)

    if account_id is None:
        reason = "account_id is required to evaluate a stored YouTube analytics credential."
    elif not credential_found:
        reason = "YouTube OAuth credential was not found for this account."
    elif missing_scopes:
        reason = "YouTube OAuth credential does not include analytics read scopes."
    else:
        reason = None

    return {
        "ready": ready,
        "credential_ready": credential_ready,
        "collector_registered": True,
        "collector_enabled": collector_enabled,
        "credential_mode": "oauth",
        "credential_source": credential_source,
        "credential_found": credential_found,
        "configured_scopes": sorted(configured_scopes),
        "required_scopes": sorted(required_scopes),
        "missing_scopes": missing_scopes,
        "requires_reauthorization": bool(account_id is not None and credential_found and missing_scopes),
        "legacy_scope_assumption": legacy_scope_assumption,
        "reason": reason,
    }


READINESS_HANDLERS = {
    "youtube": _youtube_readiness,
}


class AnalyticsCollector:
    """Platform-neutral external analytics collection boundary.

    Platform capability metadata lives in the Data Center. Provider-specific
    readiness checks are registered here so adding a future platform does not
    require changing the Data Center storage model.

    A collector that is unavailable or not authorized must fail explicitly;
    it must never fabricate zero traffic and persist that as real analytics.
    """

    def __init__(self, youtube_client_factory=YouTubeAnalyticsAPIClient):
        self.youtube_client_factory = youtube_client_factory

    def readiness(self, platform, account_id=None):
        normalized = (platform or "").strip().lower()
        capability = get_platform_capability(normalized)

        if capability is None:
            return {
                "platform": normalized or None,
                "ready": False,
                "collector_registered": False,
                "reason": "platform capability is not registered",
            }

        base = {
            "platform": normalized,
            "ready": False,
            "collector_registered": normalized in READINESS_HANDLERS,
            "analytics_supported": capability["analytics_supported"],
            "metric_types": capability["metric_types"],
        }

        if not capability["analytics_supported"]:
            base["reason"] = "analytics capability is not enabled for this platform"
            return base

        handler = READINESS_HANDLERS.get(normalized)
        if handler is None:
            base["reason"] = "analytics collector adapter is not registered for this platform"
            return base

        base.update(handler(account_id=account_id))
        base["platform"] = normalized
        base["analytics_supported"] = capability["analytics_supported"]
        base["metric_types"] = capability["metric_types"]
        return base

    def _collect_youtube(
        self,
        video_id,
        *,
        account_id,
        content_id=None,
        start_date=None,
        end_date=None,
    ):
        token = get_token(account_id)
        if not token:
            raise AnalyticsCollectionNotReady(
                f"YouTube OAuth credential not found for account_id {account_id}"
            )

        oauth_provider = YouTubeOAuthProvider(scope_profile="analytics")
        valid_token, refreshed = oauth_provider.ensure_valid_token(token)
        if refreshed:
            update_token(
                account_id,
                {
                    "provider": "youtube",
                    **valid_token,
                },
            )

        credentials = oauth_provider.build_google_credentials(valid_token)
        client = self.youtube_client_factory()
        client.initialize(credentials)
        result = client.collect_video_metrics(
            video_id,
            start_date=start_date,
            end_date=end_date,
        )

        metric = AnalyticsMetric(
            video_id=video_id,
            content_id=content_id or video_id,
            platform="youtube",
            account_id=account_id,
            source="youtube_analytics_api",
            views=result.get("views", 0),
            watch_time=result.get("watch_time", 0),
            average_view_duration=result.get("average_view_duration"),
            retention=result.get("retention"),
            likes=result.get("likes", 0),
            comments=result.get("comments", 0),
            shares=result.get("shares", 0),
        )
        return save_metric(metric)

    def collect(self, video_id, platform, account_id=None, **kwargs):
        normalized = (platform or "").strip().lower()
        status = self.readiness(normalized, account_id=account_id)
        if not status.get("ready"):
            raise AnalyticsCollectionNotReady(
                status.get("reason") or "analytics collection is not ready"
            )

        if normalized == "youtube":
            return self._collect_youtube(
                video_id,
                account_id=account_id,
                content_id=kwargs.get("content_id"),
                start_date=kwargs.get("start_date"),
                end_date=kwargs.get("end_date"),
            )

        raise AnalyticsCollectionNotReady(
            f"analytics collection adapter is not implemented for platform {normalized}"
        )
