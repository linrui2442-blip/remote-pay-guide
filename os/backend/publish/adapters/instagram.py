class InstagramAdapter:
    def __init__(self):
        self.status = "initialized"

    def initialize(self):
        self.status = "ready"
        return {
            "platform": "instagram",
            "status": "ready"
        }

    def publish_video(self, video_asset, account_id=None):
        return {
            "platform": "instagram",
            "status": "simulated"
        }

    def get_status(self):
        return {
            "platform": "instagram",
            "status": "ready"
        }
