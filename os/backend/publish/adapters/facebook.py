from datetime import datetime, timezone
from urllib.parse import urlparse
import json
import re
import requests

from accounts.manager import get_account
from oauth.manager import get_token
from oauth.meta_bindings import get_binding
from oauth.providers.meta import FACEBOOK_PUBLISH_SCOPES, MetaOAuthProvider
from oauth.meta_runtime_config import meta_runtime_config


def resolve_page_access_token(account_id, page_id, user_access_token, transport):
    return MetaOAuthProvider(platform="facebook").resolve_page_access_token(
        account_id, page_id, access_token=user_access_token, transport=transport
    )


class FacebookAdapter:
    platform_name = "facebook"

    def __init__(self, transport=None, live_publish_enabled=None):
        self.status = "initialized"
        self.transport = transport or requests
        config = meta_runtime_config()
        self.live_publish_enabled = bool(config.get("facebook_live_publish_enabled")) if live_publish_enabled is None else bool(live_publish_enabled)
        self.api_version = config.get("graph_api_version") or "v26.0"

    def initialize(self):
        # Preserve the legacy registry status while the production gate is closed.
        self.status = "placeholder"
        return self.get_status()

    def publish_video(self, video_asset, account_id=None, *, title="", description="", provider_operation_id=None, provider_operation_status=None, operation_callback=None, before_write=None):
        if not self.live_publish_enabled:
            return {"platform": "facebook", "status": "simulated", "error": "Facebook live OS publishing adapter is not configured"}
        return self.publish_reel_via_graph(video_asset, account_id, title=title, description=description, provider_operation_id=provider_operation_id, provider_operation_status=provider_operation_status, operation_callback=operation_callback, before_write=before_write)

    @staticmethod
    def _safe_error(error, secrets=None):
        text = str(error)
        for secret in secrets or ():
            if secret: text = text.replace(str(secret), "[REDACTED]")
        text = re.sub(r"(?i)(Bearer|OAuth)\s+[^\s,;]+", "[REDACTED_CREDENTIAL]", text)
        text = re.sub(r"(?i)(access_token|client_secret|authorization)=([^\s&;,]+)", r"\1=[REDACTED]", text)
        return text

    @staticmethod
    def _video_url(video_asset):
        value = video_asset.get("asset_url") or video_asset.get("location")
        parsed = urlparse(str(value or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Facebook Reels requires a public http(s) video URL")
        return value

    def get_account_readiness(self, account_id):
        account = get_account(account_id) if account_id is not None else None
        binding = get_binding(account_id) if account_id is not None else None
        token = get_token(account_id) if account_id is not None else None
        missing = []
        if not account or str(account.get("platform")).lower() != "facebook": missing.append("facebook_account")
        if not binding or str(binding.get("platform")).lower() != "facebook" or not binding.get("page_id"): missing.append("facebook_binding")
        if not token or token.get("provider") not in {"facebook", "meta"} or not token.get("access_token"): missing.append("facebook_access_token")
        scopes = token.get("scopes") if token else []
        if isinstance(scopes, str):
            try: scopes = json.loads(scopes)
            except Exception: scopes = scopes.split()
        missing_scopes = sorted(set(FACEBOOK_PUBLISH_SCOPES) - set(scopes or []))
        if missing_scopes: missing.append("scopes")
        if token and token.get("expires_at"):
            try:
                expiry = datetime.fromisoformat(str(token["expires_at"]).replace("Z", "+00:00"))
                if expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= datetime.now(timezone.utc): missing.append("expired_token")
            except (TypeError, ValueError): missing.append("invalid_token_expiry")
        return {"ready": not missing, "account_found": bool(account), "binding_found": bool(binding), "token_found": bool(token), "missing_scopes": missing_scopes, "reason": None if not missing else "Facebook publish readiness failed closed: " + ", ".join(missing)}

    def publish_reel_via_graph(self, video_asset, account_id, *, title="", description="", transport=None, provider_operation_id=None, provider_operation_status=None, operation_callback=None, before_write=None):
        readiness = self.get_account_readiness(account_id)
        if not readiness["ready"]: raise RuntimeError(readiness["reason"])
        url = self._video_url(video_asset)
        token = get_token(account_id); binding = get_binding(account_id); http = transport or self.transport
        page_token = resolve_page_access_token(account_id, binding["page_id"], token["access_token"], http)
        sensitive = [token.get("access_token"), page_token]
        headers = {"Authorization": f"OAuth {page_token}"}; base = f"https://graph.facebook.com/{self.api_version}"
        video_id = provider_operation_id; state = str(provider_operation_status or "").upper()
        safety = {'allow_redirects': False} if before_write else {}
        try:
            if state == "PUBLISHED": return {"platform": "facebook", "status": "published", "video_id": video_id, "provider_operation_id": video_id, "provider_operation_status": "PUBLISHED"}
            upload_url = None
            if not video_id:
                if before_write:
                    before_write('facebook_start')
                response = http.post(f"{base}/me/video_reels", params={"upload_phase": "start"}, headers=headers, timeout=30, **safety); response.raise_for_status(); payload = response.json() or {}; video_id, upload_url = payload.get("video_id"), payload.get("upload_url")
                if not video_id or not upload_url: raise RuntimeError("Facebook Reels start response missing video_id or upload_url")
                if operation_callback: operation_callback(video_id, "CREATED")
                state = "CREATED"
            # A fresh G5 start already owns its upload destination. Do not use
            # the legacy resume probe to infer upload state before uploading.
            # Interrupted G5 operations are reconciled locally, never resumed
            # by calling this write method again.
            if state == "CREATED" and (not before_write or provider_operation_id):
                probe = http.get(f"{base}/{video_id}", params={"fields": "status"}, headers=headers, timeout=30, **safety); probe.raise_for_status(); remote = (probe.json() or {}).get("status")
                if remote in {"UPLOADED", "FINISHED", "PUBLISHED"}: state = "UPLOADED"
                elif remote not in {"CREATED", "IN_PROGRESS", "PROCESSING"}: raise RuntimeError("Facebook Reels remote upload state is ambiguous")
            if state != "UPLOADED":
                if not upload_url: raise RuntimeError("Facebook Reels upload URL is unavailable")
                if before_write:
                    parsed = urlparse(upload_url)
                    if (parsed.scheme != 'https' or parsed.hostname != 'rupload.facebook.com'
                            or parsed.port not in (None, 443) or parsed.username or parsed.password
                            or '\\' in upload_url or any(ord(c) <= 32 for c in upload_url)):
                        raise RuntimeError('Facebook upload destination invalid')
                    before_write('facebook_upload')
                uploaded = http.post(upload_url, params={}, headers={**headers, "file_url": url}, timeout=30, **safety); uploaded.raise_for_status()
                if before_write and (uploaded.json() or {}).get('success') is not True:
                    raise RuntimeError('Facebook upload acknowledgement missing')
                if operation_callback: operation_callback(video_id, "UPLOADED")
            if before_write:
                before_write('facebook_finish')
            finished = http.post(f"{base}/me/video_reels", params={"video_id": video_id, "upload_phase": "finish", "video_state": "PUBLISHED", "title": title or "", "description": description or ""}, headers=headers, timeout=30, **safety); finished.raise_for_status()
            if before_write and (finished.json() or {}).get('success') is not True:
                raise RuntimeError('Facebook finish acknowledgement missing')
            if operation_callback: operation_callback(video_id, "PUBLISHED")
            return {"platform": "facebook", "status": "published", "video_id": video_id, "provider_operation_id": video_id, "provider_operation_status": "PUBLISHED"}
        except Exception as exc:
            raise RuntimeError(self._safe_error(exc, sensitive)) from None

    def get_status(self):
        return {"platform": "facebook", "status": self.status, "implementation_ready": True, "configuration_ready": self.live_publish_enabled, "publish_ready": self.live_publish_enabled, "reason": None if self.live_publish_enabled else "Facebook live OS publishing adapter is not configured", "execution_mode": "live_test" if self.live_publish_enabled else "simulated"}
