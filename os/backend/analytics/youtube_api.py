from datetime import date, timedelta

from googleapiclient.discovery import build


YOUTUBE_ANALYTICS_METRICS = (
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "averageViewPercentage",
    "likes",
    "comments",
    "shares",
)


class YouTubeAnalyticsAPIClient:
    """Small YouTube Analytics API v2 client used by the OS collector.

    YouTube reports estimatedMinutesWatched in minutes. The OS normalizes
    watch_time to seconds so it shares the same unit as average_view_duration.
    """

    def __init__(self, service=None):
        self.service = service

    def initialize(self, credentials=None):
        if self.service is None:
            if credentials is None:
                raise RuntimeError("YouTube Analytics credentials are required")
            self.service = build(
                "youtubeAnalytics",
                "v2",
                credentials=credentials,
                cache_discovery=False,
            )
        return {"platform": "youtube", "status": "ready"}

    @staticmethod
    def _resolve_window(start_date=None, end_date=None):
        resolved_end = end_date or date.today().isoformat()
        if start_date:
            resolved_start = start_date
        else:
            resolved_start = (date.fromisoformat(resolved_end) - timedelta(days=28)).isoformat()
        return resolved_start, resolved_end

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

    def collect_video_metrics(self, video_id, start_date=None, end_date=None):
        if not self.service:
            raise RuntimeError("YouTube Analytics API client is not initialized")
        if not video_id:
            raise ValueError("video_id is required")

        resolved_start, resolved_end = self._resolve_window(start_date, end_date)
        response = self.service.reports().query(
            ids="channel==MINE",
            startDate=resolved_start,
            endDate=resolved_end,
            metrics=",".join(YOUTUBE_ANALYTICS_METRICS),
            filters=f"video=={video_id}",
        ).execute()

        metrics = self.normalize_response(response)
        metrics.update(
            {
                "start_date": resolved_start,
                "end_date": resolved_end,
            }
        )
        return metrics
