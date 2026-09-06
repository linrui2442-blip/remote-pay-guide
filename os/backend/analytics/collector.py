from data.platform_capabilities import get_platform_capability
from oauth.providers.youtube import YOUTUBE_UPLOAD_SCOPE


YOUTUBE_READ_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
YOUTUBE_ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"


class AnalyticsCollectionNotReady(RuntimeError):
    pass


def _youtube_readiness():
    configured_scopes = {YOUTUBE_UPLOAD_SCOPE}
    required_scopes = {YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE}
    missing_scopes = sorted(required_scopes - configured_scopes)
    return {
        "ready": not missing_scopes,
        "collector_registered": True,
        "credential_mode": "oauth",
        "configured_scopes": sorted(configured_scopes),
        "required_scopes": sorted(required_scopes),
        "missing_scopes": missing_scopes,
        "requires_reauthorization": bool(missing_scopes),
        "reason": (
            "YouTube OAuth is currently upload-only; analytics read scopes are required."
            if missing_scopes
            else None
        ),
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

    def readiness(self, platform):
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

        base.update(handler())
        base["platform"] = normalized
        base["analytics_supported"] = capability["analytics_supported"]
        base["metric_types"] = capability["metric_types"]
        return base

    def collect(self, video_id, platform, **kwargs):
        status = self.readiness(platform)
        if not status.get("ready"):
            raise AnalyticsCollectionNotReady(
                status.get("reason") or "analytics collection is not ready"
            )

        raise AnalyticsCollectionNotReady(
            "analytics credential is ready but the live platform collector has not been enabled"
        )
