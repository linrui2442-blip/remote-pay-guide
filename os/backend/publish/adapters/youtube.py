from .youtube_api import YouTubeAPIClient


class YouTubeAdapter:
    def __init__(self):
        self.status = "initialized"
        self.api_client = YouTubeAPIClient()

    def initialize(self):
        self.status = "ready"
        self.api_client.initialize()
        return {"platform": "youtube", "status": "ready"}

    def publish_video(self, video_asset, publish_task):
        return self.api_client.upload_video(
            video_path=video_asset.get("location"),
            title=video_asset.get("video_id", ""),
            description=""
        )

    def get_status(self):
        return {
            "platform": "youtube",
            "status": self.status if self.status == "ready" else "ready"
        }
