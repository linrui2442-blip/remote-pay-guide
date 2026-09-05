class YouTubeAdapter:
    def __init__(self):
        self.status = "initialized"

    def initialize(self):
        self.status = "ready"
        return {"platform": "youtube", "status": "ready"}

    def publish_video(self, video_asset, publish_task):
        return {
            "platform": "youtube",
            "status": "simulated"
        }

    def get_status(self):
        return {
            "platform": "youtube",
            "status": self.status if self.status == "ready" else "ready"
        }
