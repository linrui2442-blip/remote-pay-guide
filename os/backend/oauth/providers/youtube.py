import os
import secrets
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_READ_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
YOUTUBE_ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"

YOUTUBE_SCOPE_PROFILES = {
    "publish": [YOUTUBE_UPLOAD_SCOPE],
    "analytics": [YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE],
    "full": [YOUTUBE_UPLOAD_SCOPE, YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE],
}

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class YouTubeOAuthConfigurationError(RuntimeError):
    pass


def normalize_scope_profile(scope_profile):
    profile = (scope_profile or "publish").strip().lower()
    if profile not in YOUTUBE_SCOPE_PROFILES:
        raise ValueError(
            "unsupported YouTube OAuth scope profile: "
            f"{scope_profile}; expected one of {', '.join(sorted(YOUTUBE_SCOPE_PROFILES))}"
        )
    return profile


class YouTubeOAuthProvider:
    def __init__(
        self,
        client_id=None,
        client_secret=None,
        redirect_uri=None,
        scope_profile="publish",
    ):
        self.client_id = (
            client_id
            or os.getenv("YOUTUBE_OAUTH_CLIENT_ID")
            or os.getenv("GOOGLE_CLIENT_ID")
        )
        self.client_secret = (
            client_secret
            or os.getenv("YOUTUBE_OAUTH_CLIENT_SECRET")
            or os.getenv("GOOGLE_CLIENT_SECRET")
        )
        self.redirect_uri = (
            redirect_uri
            or os.getenv("YOUTUBE_OAUTH_REDIRECT_URI")
            or os.getenv("GOOGLE_REDIRECT_URI")
        )
        self.scope_profile = normalize_scope_profile(scope_profile)

    @property
    def scopes(self):
        return list(YOUTUBE_SCOPE_PROFILES[self.scope_profile])

    def _require_config(self, require_redirect=True):
        missing = []
        if not self.client_id:
            missing.append("YOUTUBE_OAUTH_CLIENT_ID")
        if not self.client_secret:
            missing.append("YOUTUBE_OAUTH_CLIENT_SECRET")
        if require_redirect and not self.redirect_uri:
            missing.append("YOUTUBE_OAUTH_REDIRECT_URI")
        if missing:
            raise YouTubeOAuthConfigurationError(
                "missing YouTube OAuth configuration: " + ", ".join(missing)
            )

    def _client_config(self):
        self._require_config(require_redirect=True)
        return {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": GOOGLE_AUTH_URI,
                "token_uri": GOOGLE_TOKEN_URI,
                "redirect_uris": [self.redirect_uri],
            }
        }

    @staticmethod
    def _expiry_to_iso(expiry):
        if not expiry:
            return None
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _parse_expiry(value):
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def get_authorization_url(self, client_id=None, redirect_uri=None, state=None):
        # Keep google-auth-oauthlib optional for unrelated OS paths that only
        # import the publishing registry. It is required only when OAuth is
        # actually initiated.
        from google_auth_oauthlib.flow import Flow

        if client_id:
            self.client_id = client_id
        if redirect_uri:
            self.redirect_uri = redirect_uri

        flow = Flow.from_client_config(
            self._client_config(),
            scopes=self.scopes,
            state=state,
        )
        flow.redirect_uri = self.redirect_uri
        authorization_url, generated_state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state or secrets.token_urlsafe(32),
        )
        return {
            "authorization_url": authorization_url,
            "state": generated_state,
            "scope_profile": self.scope_profile,
            "scopes": self.scopes,
        }

    def exchange_code(self, authorization_code: str, state=None):
        from google_auth_oauthlib.flow import Flow

        if not authorization_code:
            raise ValueError("authorization_code is required")

        flow = Flow.from_client_config(
            self._client_config(),
            scopes=self.scopes,
            state=state,
        )
        flow.redirect_uri = self.redirect_uri
        flow.fetch_token(code=authorization_code)
        credentials = flow.credentials
        granted_scopes = list(credentials.scopes or self.scopes)

        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "expires_at": self._expiry_to_iso(credentials.expiry),
            "scopes": sorted(set(granted_scopes)),
            "scope_profile": self.scope_profile,
        }

    def _build_credentials(self, token_data):
        self._require_config(require_redirect=False)
        scopes = token_data.get("scopes") or self.scopes
        return Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=GOOGLE_TOKEN_URI,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=scopes,
            expiry=self._parse_expiry(token_data.get("expires_at")),
        )

    def refresh_token(self, refresh_token: str, scopes=None):
        if not refresh_token:
            raise ValueError("refresh_token is required")
        credentials = self._build_credentials(
            {
                "access_token": None,
                "refresh_token": refresh_token,
                "expires_at": None,
                "scopes": scopes or self.scopes,
            }
        )
        credentials.refresh(Request())
        refreshed_scopes = list(credentials.scopes or scopes or self.scopes)
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token or refresh_token,
            "expires_at": self._expiry_to_iso(credentials.expiry),
            "scopes": sorted(set(refreshed_scopes)),
        }

    def ensure_valid_token(self, token_data):
        if not token_data:
            raise RuntimeError("YouTube OAuth credential not found")

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expiry = self._parse_expiry(token_data.get("expires_at"))
        scopes = token_data.get("scopes") or self.scopes
        now = datetime.now(timezone.utc)

        should_refresh = False
        if not access_token:
            should_refresh = True
        elif refresh_token and expiry is None:
            # Older credential rows did not reliably persist expiry.
            should_refresh = True
        elif refresh_token and expiry and (expiry - now).total_seconds() <= 60:
            should_refresh = True

        if should_refresh:
            if not refresh_token:
                raise RuntimeError("YouTube OAuth access token is unavailable and no refresh token exists")
            refreshed = self.refresh_token(refresh_token, scopes=scopes)
            return refreshed, True

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": token_data.get("expires_at"),
            "scopes": scopes,
        }, False

    def build_google_credentials(self, token_data):
        return self._build_credentials(token_data)
