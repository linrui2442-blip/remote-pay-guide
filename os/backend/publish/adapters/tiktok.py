class TikTokAdapter:
    def __init__(self):
        self.status = "initialized"

    def initialize(self):
        self.status = "ready"
        return {
            "platform": "tiktok",
            "status": "ready"
        }

    def publish_video(self, video_asset, account_id=None):
        return {
            "platform": "tiktok",
            "status": "simulated"
        }

    def get_status(self):
        return {
            "platform": "tiktok",
            "status": "ready"
        }
