from datetime import date, timedelta

import requests

from analytics.errors import AnalyticsNoData
from integrations.google_transport import build_authorized_session


YOUTUBE_ANALYTICS_METRICS = (
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "averageViewPercentage",
    "likes",
    "comments",
    "shares",
)
YOUTUBE_CHANNEL_ANALYTICS_METRICS = YOUTUBE_ANALYTICS_METRICS + (
    "subscribersGained",
    "subscribersLost",
)


class YouTubeAnalyticsAPIClient:
    """Small YouTube Analytics API v2 client used by the OS collector.

    YouTube ``startDate``/``endDate`` values are inclusive reporting dates.
    Per Google's Analytics dimension contract, each reporting day runs from
    midnight to 23:59 Pacific time (including DST), not on UTC boundaries.
    The provider-neutral OS date is passed through unchanged and this adapter
    owns that provider interpretation.

    YouTube reports estimatedMinutesWatched in minutes. The OS normalizes
    watch_time to seconds so it shares the same unit as average_view_duration.
    Live calls use the same explicit proxy-aware Google requests transport as
    YouTube content sync.
    """

    API_URL = "https://youtubeanalytics.googleapis.com/v2/reports"

    def __init__(self, service=None, session=None):
        self.service = service
        self.session = session

    def initialize(self, credentials=None):
        if self.service is None and self.session is None:
            if credentials is None:
                raise RuntimeError("YouTube Analytics credentials are required")
            self.session = build_authorized_session(credentials)
        return {"platform": "youtube", "status": "ready"}

    @staticmethod
    def _resolve_window(start_date=None, end_date=None):
        # Use complete days by default. The range is 28 calendar days,
        # inclusive of both start and end dates.
        resolved_end_date = (
            date.fromisoformat(end_date)
            if end_date
            else date.today() - timedelta(days=1)
        )
        resolved_start_date = (
            date.fromisoformat(start_date)
            if start_date
            else resolved_end_date - timedelta(days=27)
        )
        if resolved_start_date > resolved_end_date:
            raise ValueError("start_date must be on or before end_date")
        return resolved_start_date.isoformat(), resolved_end_date.isoformat()

    @staticmethod
    def _row_map(response):
        headers = response.get("columnHeaders") or []
        rows = response.get("rows") or []
        if not rows:
            return {}
        names = [header.get("name") for header in headers]
        return dict(zip(names, rows[0]))

    @staticmethod
    def _int(value):
        try:
            return int(round(float(value or 0)))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _float(value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def normalize_response(cls, response):
        row = cls._row_map(response or {})
        estimated_minutes = cls._float(row.get("estimatedMinutesWatched")) or 0.0
        return {
            "views": cls._int(row.get("views")),
            "watch_time": cls._int(estimated_minutes * 60),
            "average_view_duration": cls._float(row.get("averageViewDuration")),
            "retention": cls._float(row.get("averageViewPercentage")),
            "likes": cls._int(row.get("likes")),
            "comments": cls._int(row.get("comments")),
            "shares": cls._int(row.get("shares")),
        }

    @classmethod
    def normalize_channel_response(cls, response):
        normalized = cls.normalize_response(response)
        row = cls._row_map(response or {})
        normalized.update(
            {
                "subscribers_gained": cls._int(row.get("subscribersGained")),
                "subscribers_lost": cls._int(row.get("subscribersLost")),
            }
        )
        return normalized

    @staticmethod
    def _error_detail(response):
        try:
            payload = response.json()
            message = payload.get("error", {}).get("message")
            if message:
                return message
        except Exception:
            pass
        return response.text[:300] if getattr(response, "text", None) else "unknown Google API error"

    def _query_via_requests(self, params):
        try:
            response = self.session.get(self.API_URL, params=params, timeout=(10, 30))
            response.raise_for_status()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            raise RuntimeError(
                "Google YouTube Analytics network/proxy request failed. Check Remote Pay Guide OS "
                "System Settings -> Proxy and confirm the local HTTP/Mixed proxy port is running."
            ) from exc
        except requests.exceptions.RequestException as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                raise RuntimeError(
                    f"Google YouTube Analytics request failed ({response.status_code}): "
                    f"{self._error_detail(response)}"
                ) from exc
            raise RuntimeError(f"Google YouTube Analytics request failed: {exc}") from exc
        return response.json()

    def _query(self, params):
        if self.service is not None:
            return self.service.reports().query(**params).execute()
        return self._query_via_requests(params)

    def collect_video_metrics(self, video_id, start_date=None, end_date=None):
        if not self.service and not self.session:
            raise RuntimeError("YouTube Analytics API client is not initialized")
        if not video_id:
            raise ValueError("video_id is required")

        resolved_start, resolved_end = self._resolve_window(start_date, end_date)
        params = {
            "ids": "channel==MINE",
            "startDate": resolved_start,
            "endDate": resolved_end,
            "metrics": ",".join(YOUTUBE_ANALYTICS_METRICS),
            "filters": f"video=={video_id}",
        }
        response = self._query(params)
        if not (response or {}).get("rows"):
            raise AnalyticsNoData(
                "YouTube Analytics returned no row "
                f"(platform=youtube, video_id={video_id}, "
                f"start_date={resolved_start}, end_date={resolved_end})"
            )

        metrics = self.normalize_response(response)
        metrics.update(
            {
                "start_date": resolved_start,
                "end_date": resolved_end,
            }
        )
        return metrics

    def collect_channel_metrics(self, start_date=None, end_date=None):
        if not self.service and not self.session:
            raise RuntimeError("YouTube Analytics API client is not initialized")

        resolved_start, resolved_end = self._resolve_window(start_date, end_date)
        params = {
            "ids": "channel==MINE",
            "startDate": resolved_start,
            "endDate": resolved_end,
            "metrics": ",".join(YOUTUBE_CHANNEL_ANALYTICS_METRICS),
        }
        response = self._query(params)
        if not (response or {}).get("rows"):
            raise AnalyticsNoData(
                "YouTube Analytics returned no row "
                f"(platform=youtube, channel=MINE, "
                f"start_date={resolved_start}, end_date={resolved_end})"
            )
        metrics = self.normalize_channel_response(response)
        metrics.update(
            {
                "start_date": resolved_start,
                "end_date": resolved_end,
            }
        )
        return metrics
