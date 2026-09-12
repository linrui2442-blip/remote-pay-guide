from urllib.parse import urlparse
from datetime import datetime, timezone
import json
import re
import requests
from accounts.manager import get_account
from oauth.manager import get_token
from oauth.meta_bindings import get_binding
from oauth.meta_runtime_config import meta_runtime_config
from oauth.providers.meta import INSTAGRAM_PUBLISH_SCOPES

class InstagramAdapter:
    platform_name = "instagram"

    def __init__(self, transport=None, live_publish_enabled=None):
        self.status = "initialized"
        self.transport = transport or requests
        config = meta_runtime_config()
        self.live_publish_enabled = bool(config.get("instagram_live_publish_enabled")) if live_publish_enabled is None else bool(live_publish_enabled)
        self.api_version = config.get("graph_api_version") or "v26.0"

    def initialize(self):
        self.status = "ready"
        return self.get_status()

    def publish_video(self, video_asset, account_id=None, *, caption="", provider_operation_id=None, provider_operation_status=None, operation_callback=None):
        if self.live_publish_enabled:
            return self.publish_reel_via_graph(video_asset, account_id, caption, provider_operation_id=provider_operation_id, provider_operation_status=provider_operation_status, operation_callback=operation_callback)
        # Keep the legacy adapter method available for compatibility tests, but
        # Publish Center orchestration must never treat this as a live publish.
        return {
            "platform": "instagram",
            "status": "simulated",
            "error": "Instagram live OS publishing adapter is not configured",
        }

    @staticmethod
    def _safe_error(error, secrets=None):
        text = str(error)
        for secret in secrets or ():
            if secret:
                text = text.replace(str(secret), "[REDACTED]")
        text = re.sub(r"(?i)Bearer\s+[^\s,;]+", "[REDACTED_CREDENTIAL]", text)
        text = re.sub(r"(?i)(access_token|client_secret|authorization_code|fb_exchange_token)=([^\s&;,]+)", r"\1=[REDACTED]", text)
        text = re.sub(r"(?i)Authorization", "[REDACTED_HEADER]", text)
        return text

    @staticmethod
    def _video_url(video_asset):
        value = video_asset.get("asset_url") or video_asset.get("location")
        parsed = urlparse(str(value or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Instagram Reels requires a public http(s) video URL")
        return value

    def get_account_readiness(self, account_id):
        account = get_account(account_id) if account_id is not None else None
        binding = get_binding(account_id) if account_id is not None else None
        token = get_token(account_id) if account_id is not None else None
        missing = []
        if not account or str(account.get("platform")).lower() != "instagram":
            missing.append("instagram_account")
        if not binding or str(binding.get("platform")).lower() != "instagram" or not binding.get("instagram_user_id"):
            missing.append("instagram_binding")
        if not token or token.get("provider") != "instagram" or not token.get("access_token"):
            missing.append("instagram_access_token")
        scopes = token.get("scopes") if token else []
        if isinstance(scopes, str):
            try:
                scopes = json.loads(scopes)
            except (TypeError, ValueError, json.JSONDecodeError):
                scopes = scopes.split()
        missing_scopes = sorted(set(INSTAGRAM_PUBLISH_SCOPES) - set(scopes or []))
        if missing_scopes:
            missing.append("scopes")
        if token and token.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(str(token["expires_at"]).replace("Z", "+00:00"))
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= datetime.now(timezone.utc):
                    missing.append("expired_token")
            except (TypeError, ValueError):
                missing.append("invalid_token_expiry")
        return {"ready": not missing, "account_found": bool(account), "binding_found": bool(binding), "token_found": bool(token), "publish_scope_granted": not missing_scopes, "missing_scopes": missing_scopes, "reason": None if not missing else "Instagram publish readiness failed closed: " + ", ".join(missing)}

    def publish_reel_via_graph(self, video_asset, account_id, caption="", transport=None, *, provider_operation_id=None, provider_operation_status=None, operation_callback=None, sleep_fn=None, max_attempts=5, poll_interval_seconds=2):
        """Documented two-step Reels flow; transport is injectable for tests."""
        readiness = self.get_account_readiness(account_id)
        if not readiness["ready"]:
            raise RuntimeError(readiness["reason"])
        url = self._video_url(video_asset)
        token = get_token(account_id)
        ig_user_id = get_binding(account_id)["instagram_user_id"]
        base = f"https://graph.facebook.com/{self.api_version}/{ig_user_id}"
        http = transport or self.transport
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        sensitive = [token.get("access_token")]
        if provider_operation_id:
            creation_id = provider_operation_id
            if str(provider_operation_status or "").upper() == "PUBLISHED":
                return {"platform": "instagram", "status": "published", "video_id": None, "url": None, "provider_operation_id": creation_id, "provider_operation_status": "PUBLISHED"}
            created_new = False
        else:
            try:
                container = http.post(f"{base}/media", params={"media_type": "REELS", "video_url": url, "caption": caption or ""}, headers=headers, timeout=30)
                container.raise_for_status()
            except Exception as exc:
                raise RuntimeError(self._safe_error(exc, sensitive)) from None
            creation_id = container.json().get("id")
            created_new = True
        if not creation_id:
            raise RuntimeError("Instagram Reels container response did not include an id")
        if operation_callback and created_new:
            operation_callback(creation_id, "CREATED")
        sleep_fn = sleep_fn or __import__("time").sleep
        state = None
        for attempt in range(max(1, int(max_attempts))):
            try:
                state_response = http.get(f"https://graph.facebook.com/{self.api_version}/{creation_id}", params={"fields": "status_code,status"}, headers=headers, timeout=30)
                state_response.raise_for_status()
                state_payload = state_response.json()
            except Exception as exc:
                raise RuntimeError(self._safe_error(exc, sensitive)) from None
            state = state_payload.get("status_code") or state_payload.get("status")
            if operation_callback:
                operation_callback(creation_id, state)
            if state == "FINISHED":
                break
            if state == "PUBLISHED":
                return {"platform": "instagram", "status": "published", "video_id": None, "url": None, "provider_operation_id": creation_id, "provider_operation_status": "PUBLISHED"}
            if state in {"ERROR", "EXPIRED"}:
                raise RuntimeError(f"Instagram media container is {state.lower()}")
            if state != "IN_PROGRESS":
                raise RuntimeError("Instagram media container returned an unknown state")
            if attempt + 1 < max_attempts:
                sleep_fn(poll_interval_seconds)
        if state != "FINISHED":
            raise RuntimeError("Instagram media container polling timed out")
        try:
            published = http.post(f"{base}/media_publish", params={"creation_id": creation_id}, headers=headers, timeout=30)
            published.raise_for_status()
        except Exception as exc:
            raise RuntimeError(self._safe_error(exc, sensitive)) from None
        media_id = published.json().get("id")
        if not media_id:
            raise RuntimeError("Instagram publish response did not include a media id")
        if operation_callback:
            operation_callback(creation_id, "PUBLISHED")
        return {"platform": "instagram", "status": "published", "video_id": media_id, "url": None, "provider_operation_id": creation_id, "provider_operation_status": "PUBLISHED"}

    def get_status(self):
        return {
            "platform": "instagram",
            "status": self.status,
            "publish_ready": self.live_publish_enabled,
            "implementation_ready": True,
            "configuration_ready": self.live_publish_enabled,
            "account_ready": None,
            "reason": None if self.live_publish_enabled else "Instagram live OS publishing adapter is not configured",
            "execution_mode": "live_test" if self.live_publish_enabled else "simulated",
        }
