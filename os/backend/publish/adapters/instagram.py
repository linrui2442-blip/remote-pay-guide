from urllib.parse import urlparse
import requests
from accounts.manager import get_account
from oauth.manager import get_token
from oauth.meta_bindings import get_binding
from oauth.meta_runtime_config import meta_runtime_config

class InstagramAdapter:
    platform_name = "instagram"

    def __init__(self, transport=None):
        self.status = "initialized"
        self.transport = transport or requests
        self.api_version = meta_runtime_config().get("graph_api_version") or "v26.0"

    def initialize(self):
        self.status = "ready"
        return self.get_status()

    def publish_video(self, video_asset, account_id=None):
        # Keep the legacy adapter method available for compatibility tests, but
        # Publish Center orchestration must never treat this as a live publish.
        return {
            "platform": "instagram",
            "status": "simulated",
            "error": "Instagram live OS publishing adapter is not configured",
        }

    def get_account_readiness(self, account_id):
        account = get_account(account_id) if account_id is not None else None
        binding = get_binding(account_id) if account_id is not None else None
        token = get_token(account_id) if account_id is not None else None
        ok = bool(account and str(account.get("platform")).lower() == "instagram" and binding and binding.get("instagram_user_id") and token and (token.get("access_token") or token.get("refresh_token")))
        return {"ready": ok, "account_found": bool(account), "binding_found": bool(binding), "token_found": bool(token), "reason": None if ok else "Instagram account, binding, or OAuth token is not ready"}

    def publish_reel_via_graph(self, video_asset, account_id, caption="", transport=None):
        """Documented two-step Reels flow; transport is injectable for tests."""
        readiness = self.get_account_readiness(account_id)
        if not readiness["ready"]:
            raise RuntimeError(readiness["reason"])
        url = video_asset.get("asset_url") or video_asset.get("location")
        parsed = urlparse(str(url or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Instagram Reels requires a public http(s) video URL")
        token = get_token(account_id)
        ig_user_id = get_binding(account_id)["instagram_user_id"]
        base = f"https://graph.facebook.com/{self.api_version}/{ig_user_id}"
        http = transport or self.transport
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        container = http.post(f"{base}/media", params={"media_type": "REELS", "video_url": url, "caption": caption or ""}, headers=headers, timeout=30)
        container.raise_for_status()
        creation_id = container.json().get("id")
        if not creation_id:
            raise RuntimeError("Instagram Reels container response did not include an id")
        published = http.post(f"{base}/media_publish", params={"creation_id": creation_id}, headers=headers, timeout=30)
        published.raise_for_status()
        return {"platform": "instagram", "status": "published", "video_id": published.json().get("id"), "url": None}

    def get_status(self):
        return {
            "platform": "instagram",
            "status": self.status,
            "execution_mode": "simulated",
            "publish_ready": False,
            "reason": "Instagram live OS publishing adapter is not configured",
        }
