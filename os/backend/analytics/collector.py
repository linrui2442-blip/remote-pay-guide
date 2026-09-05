class AnalyticsCollector:
    def collect(self, video_id, platform):
        return {
            "video_id": video_id,
            "platform": platform,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "watch_time": 0,
            "shares": 0,
        }
