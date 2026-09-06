from accounts.manager import get_account
from oauth.manager import get_token, update_token
from oauth.providers.youtube import YouTubeOAuthProvider

from .youtube_api import YouTubeAPIClient


class YouTubeAdapter:
    def __init__(self):
        self.status = "initialized"
        self.api_client = YouTubeAPIClient()

    def initialize(self):
        self.status = "ready"
        return {"platform": "youtube", "status": "ready"}

    def _credentials_for_account(self, account_id):
        if account_id is None:
            raise RuntimeError("YouTube PublishTask requires account_id")

        account = get_account(account_id)
        if not account:
            raise RuntimeError(f"YouTube account_id {account_id} was not found")
        if str(account.get("platform", "")).lower() != "youtube":
            raise RuntimeError(
                f"account_id {account_id} is not bound to the YouTube platform"
            )

        token = get_token(account_id)
        if not token:
            raise RuntimeError(
                f"YouTube OAuth credential not found for account_id {account_id}"
            )

        oauth_provider = YouTubeOAuthProvider()
        valid_token, refreshed = oauth_provider.ensure_valid_token(token)
        if refreshed:
            update_token(account_id, valid_token)

        return oauth_provider.build_google_credentials(valid_token)

    def publish_video(
        self,
        video_asset,
        account_id=None,
        video_path=None,
        title=None,
        description="",
        tags=None,
        privacy_status="private",
    ):
        try:
            credentials = self._credentials_for_account(account_id)
            self.api_client.initialize(credentials)
            return self.api_client.upload_video(
                video_path=video_path,
                title=title or video_asset.get("video_id") or video_asset.get("asset_id") or "Remote Pay Guide",
                description=description or "",
                tags=tags or [],
                privacy_status=privacy_status or "private",
            )
        except Exception as error:
            return {
                "platform": "youtube",
                "status": "failed",
                "error": str(error),
            }

    def get_status(self):
        return {"platform": "youtube", "status": self.status}
