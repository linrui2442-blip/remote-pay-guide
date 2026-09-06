from oauth.providers.youtube import YOUTUBE_UPLOAD_SCOPE


YOUTUBE_READ_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
YOUTUBE_ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"


class AnalyticsCollectionNotReady(RuntimeError):
    pass


class AnalyticsCollector:
    """External analytics collection boundary for the OS Data Center.

    The previous placeholder returned zero metrics, which made an unavailable
    external integration indistinguishable from real zero traffic. Until the
    platform credential has the required read scopes, collection fails
    explicitly and the Data Center keeps existing data unchanged.
    """

    def readiness(self, platform):
        platform = (platform or "").lower()

        if platform == "youtube":
            configured_scopes = {YOUTUBE_UPLOAD_SCOPE}
            required_scopes = {YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE}
            missing_scopes = sorted(required_scopes - configured_scopes)
            return {
                "platform": "youtube",
                "ready": not missing_scopes,
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

        return {
            "platform": platform or None,
            "ready": False,
            "reason": "analytics collector is not implemented for this platform",
        }

    def collect(self, video_id, platform, **kwargs):
        status = self.readiness(platform)
        if not status.get("ready"):
            raise AnalyticsCollectionNotReady(status.get("reason") or "analytics collection is not ready")

        raise AnalyticsCollectionNotReady(
            "analytics credential is ready but the live platform collector has not been enabled"
        )
