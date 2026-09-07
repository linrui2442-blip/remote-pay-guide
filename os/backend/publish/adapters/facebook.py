class FacebookAdapter:
    platform_name = "facebook"

    def __init__(self):
        self.status = "placeholder"

    def initialize(self):
        self.status = "placeholder"
        return self.get_status()

    def publish_video(self, video_asset, account_id=None):
        # Keep the legacy adapter method available for compatibility tests, but
        # Publish Center orchestration must never treat this as a live publish.
        return {
            "platform": "facebook",
            "status": "simulated",
            "error": "Facebook live OS publishing adapter is not configured",
        }

    def get_status(self):
        return {
            "platform": "facebook",
            "status": self.status,
            "execution_mode": "simulated",
            "publish_ready": False,
            "reason": "Facebook live OS publishing adapter is not configured",
        }
