class FacebookAdapter:
    def __init__(self):
        self.status = "initialized"

    def initialize(self):
        self.status = "ready"
        return {
            "platform": "facebook",
            "status": "ready"
        }

    def publish_video(self, video_asset, account_id=None):
        return {
            "platform": "facebook",
            "status": "simulated"
        }

    def get_status(self):
        return {
            "platform": "facebook",
            "status": "ready"
        }
