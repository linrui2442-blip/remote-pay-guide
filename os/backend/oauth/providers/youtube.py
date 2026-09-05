from urllib.parse import urlencode


class YouTubeOAuthProvider:
    def get_authorization_url(self, client_id: str, redirect_uri: str):
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "youtube.readonly",
        }
        return {
            "authorization_url": "https://accounts.google.com/o/oauth2/auth?" + urlencode(params)
        }

    def exchange_code(self, authorization_code: str):
        return {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "expires_at": None,
        }

    def refresh_token(self, refresh_token: str):
        return {
            "access_token": "mock_refreshed_access_token",
            "refresh_token": refresh_token,
            "expires_at": None,
        }
