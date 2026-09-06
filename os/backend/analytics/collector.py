from data.platform_capabilities import get_platform_capability
from oauth.manager import get_token
from oauth.providers.youtube import (
    YOUTUBE_ANALYTICS_SCOPE,
    YOUTUBE_READ_SCOPE,
    YOUTUBE_UPLOAD_SCOPE,
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

    if account_id is not None and not credential_found:
        reason = "YouTube OAuth credential was not found for this account."
    elif missing_scopes:
        reason = "YouTube OAuth credential does not include analytics read scopes."
    else:
        reason = "YouTube analytics credential is ready; live collection adapter is not enabled yet."

    return {
        "ready": False,
        "credential_ready": credential_ready,
        "collector_registered": True,
        "collector_enabled": False,
        "credential_mode": "oauth",
        "credential_source": credential_source,
        "credential_found": credential_found,
        "configured_scopes": sorted(configured_scopes),
        "required_scopes": sorted(required_scopes),
        "missing_scopes": missing_scopes,
        "requires_reauthorization": bool(missing_scopes),
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

    def collect(self, video_id, platform, account_id=None, **kwargs):
        status = self.readiness(platform, account_id=account_id)
        if not status.get("ready"):
            raise AnalyticsCollectionNotReady(
                status.get("reason") or "analytics collection is not ready"
            )

        raise AnalyticsCollectionNotReady(
            "analytics credential is ready but the live platform collector has not been enabled"
        )
