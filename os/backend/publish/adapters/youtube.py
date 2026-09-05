from .youtube_api import YouTubeAPIClient
from accounts.manager import get_account
from oauth.manager import get_token


class YouTubeAdapter:
    def __init__(self):
        self.status = "initialized"
        self.api_client = YouTubeAPIClient()

    def initialize(self):
        self.status = "ready"
        return {"platform": "youtube", "status": "ready"}

    def publish_video(self, video_asset, account_id=None):
        credentials = {}

        if account_id:
            account = get_account(account_id)
            token = get_token(account_id)

            if account:
                credentials["account"] = account
            if token:
                credentials["access_token"] = token.get("access_token")
                credentials["refresh_token"] = token.get("refresh_token")

        self.api_client.initialize(credentials)

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
