from datetime import datetime, timedelta, timezone

from accounts.manager import get_account
from oauth.manager import get_token, update_token
from oauth.providers.youtube import (YOUTUBE_UPLOAD_SCOPE, YOUTUBE_FORCE_SSL_SCOPE,
                                     YouTubeOAuthProvider)

from .youtube_api import YouTubeAPIClient


class YouTubeAdapter:
    platform_name = "youtube"

    def __init__(self):
        self.status = "initialized"
        self.api_client = YouTubeAPIClient()

    def initialize(self):
        self.status = "ready"
        return self.get_status()

    def get_account_readiness(self, account_id):
        """Check account/upload credential readiness without making a network call."""
        if account_id is None:
            return {
                "ready": False,
                "credential_found": False,
                "upload_scope_granted": False,
                "reason": "YouTube PublishTask requires account_id",
            }

        account = get_account(account_id)
        if not account:
            return {
                "ready": False,
                "credential_found": False,
                "upload_scope_granted": False,
                "reason": f"YouTube account_id {account_id} was not found",
            }
        if str(account.get("platform", "")).lower() != "youtube":
            return {
                "ready": False,
                "credential_found": False,
                "upload_scope_granted": False,
                "reason": f"account_id {account_id} is not bound to the YouTube platform",
            }

        token = get_token(account_id)
        if not token:
            return {
                "ready": False,
                "credential_found": False,
                "upload_scope_granted": False,
                "reason": f"YouTube OAuth credential not found for account_id {account_id}",
            }

        scopes = token.get("scopes") or []
        if isinstance(scopes, str):
            scopes = [item for item in scopes.split() if item]
        upload_scope_granted = YOUTUBE_UPLOAD_SCOPE in set(scopes)
        token_material_available = bool(
            token.get("access_token") or token.get("refresh_token")
        )

        if not token_material_available:
            reason = f"YouTube OAuth credential for account_id {account_id} has no usable token"
        elif not upload_scope_granted:
            reason = (
                f"YouTube OAuth credential for account_id {account_id} "
                "is missing youtube.upload scope"
            )
        else:
            reason = None

        return {
            "ready": token_material_available and upload_scope_granted,
            "credential_found": True,
            "upload_scope_granted": upload_scope_granted,
            "reason": reason,
        }

    def get_public_release_scope_readiness(self, account_id):
        """Local credential metadata only; never refresh or contact Google."""
        account = get_account(account_id) if account_id is not None else None
        token = get_token(account_id) if account_id is not None else None
        scopes = set(YouTubeOAuthProvider._scope_values((token or {}).get('scopes')))
        found = bool(token)
        force_ssl = YOUTUBE_FORCE_SSL_SCOPE in scopes
        full_youtube = 'https://www.googleapis.com/auth/youtube' in scopes
        return {'credential_found': found, 'force_ssl_scope_granted': force_ssl,
                'full_youtube_scope_granted': full_youtube,
                'public_release_scope_ready': bool(account and account.get('platform') == 'youtube'
                    and account.get('status') in {'connected', 'active', 'ready'}
                    and found and (force_ssl or full_youtube))}

    def _credentials_for_account(self, account_id, *, credential_refresh_authorized=True):
        readiness = self.get_account_readiness(account_id)
        if not readiness["ready"]:
            raise RuntimeError(readiness["reason"])

        token = get_token(account_id)
        oauth_provider = YouTubeOAuthProvider()
        if credential_refresh_authorized:
            valid_token, refreshed = oauth_provider.ensure_valid_token(token)
            if refreshed:
                update_token(account_id, valid_token)
        else:
            expiry = oauth_provider._parse_expiry(token.get('expires_at'))
            if (not token.get('access_token') or expiry is None
                    or expiry <= datetime.now(timezone.utc) + timedelta(minutes=5)):
                raise RuntimeError('YOUTUBE_TOKEN_REFRESH_REQUIRES_EXPLICIT_AUTHORIZATION')
            # No implicit google-auth refresh during a human-authorized upload.
            valid_token = {**token, 'refresh_token': None}
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
        before_write=None,
        operation_callback=None,
        credential_refresh_authorized=True,
    ):
        stage = 'CREDENTIAL_BUILD'
        try:
            credentials = (self._credentials_for_account(account_id)
                           if credential_refresh_authorized else
                           self._credentials_for_account(account_id, credential_refresh_authorized=False))
            # Autonomous callers may run different accounts concurrently.
            # Never share a mutable authorized session between those calls.
            client = YouTubeAPIClient() if before_write else self.api_client
            stage = 'AUTHORIZED_SESSION_BUILD'
            client.initialize(credentials)
            stage = 'VIDEO_PATH_VALIDATION'
            hooks = {} if before_write is None else {'before_write': before_write, 'operation_callback': operation_callback}
            result = client.upload_video(
                video_path=video_path,
                title=title or video_asset.get("video_id") or video_asset.get("asset_id") or "Remote Pay Guide",
                description=description or "",
                tags=tags or [],
                privacy_status=privacy_status or "private",
                **hooks,
            )
            return result
        except Exception as error:
            if before_write is not None:
                return {'platform': 'youtube', 'status': 'failed',
                        'failure_stage': stage}
            return {
                "platform": "youtube",
                "status": "failed",
                "error": str(error),
            }

    def get_status(self):
        return {
            "platform": "youtube",
            "status": self.status,
            "execution_mode": "live_api",
            "publish_ready": self.status == "ready",
            "reason": None if self.status == "ready" else "YouTube adapter is not initialized",
        }
