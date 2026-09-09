import secrets
from urllib.parse import urlencode
import requests
from config.network import configure_outbound_proxy
from oauth.manager import create_oauth_state
from oauth.meta_runtime_config import meta_runtime_config

FACEBOOK_PUBLISH_SCOPES = ["pages_show_list", "pages_read_engagement", "pages_manage_posts"]
INSTAGRAM_PUBLISH_SCOPES = ["pages_show_list", "pages_read_engagement", "instagram_basic", "instagram_content_publish"]
META_FULL_SCOPES = sorted(set(FACEBOOK_PUBLISH_SCOPES + INSTAGRAM_PUBLISH_SCOPES))

class MetaOAuthConfigurationError(RuntimeError):
    pass

class MetaOAuthProvider:
    def __init__(self, platform="facebook", **config):
        self.platform = platform.strip().lower()
        if self.platform not in {"facebook", "instagram"}: raise ValueError("unsupported Meta platform")
        self.scope_profile = config.pop("scope_profile", None)
        self.config = meta_runtime_config(**config)
        self.scope_profile = self.scope_profile or ("facebook_publish" if self.platform == "facebook" else "instagram_publish")
        self.scopes = self._scopes()

    def _scopes(self):
        if self.scope_profile == "facebook_publish": return list(FACEBOOK_PUBLISH_SCOPES)
        if self.scope_profile == "instagram_publish": return list(INSTAGRAM_PUBLISH_SCOPES)
        if self.scope_profile == "meta_full": return list(META_FULL_SCOPES)
        raise ValueError("unsupported Meta scope profile")

    def _require_config(self):
        missing = [key for key in ("app_id", "app_secret", "redirect_uri", "graph_api_version") if not self.config.get(key)]
        if missing: raise MetaOAuthConfigurationError("missing Meta OAuth configuration: " + ", ".join(missing))

    def authorization_url(self, account_id):
        self._require_config(); state = secrets.token_urlsafe(32)
        create_oauth_state(account_id, state, provider="meta", scope_profile=self.scope_profile)
        query = {"client_id": self.config["app_id"], "redirect_uri": self.config["redirect_uri"], "state": state, "scope": ",".join(self.scopes), "response_type": "code"}
        return {"authorization_url": "https://www.facebook.com/" + self.config["graph_api_version"] + "/dialog/oauth?" + urlencode(query), "state": state, "scope_profile": self.scope_profile, "scopes": self.scopes}

    def _get(self, resource, access_token, **params):
        self._require_config()
        configure_outbound_proxy()
        response = requests.get(f"https://graph.facebook.com/{self.config['graph_api_version']}/{resource}", params=params, headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
        response.raise_for_status(); return response.json()

    def _token_exchange(self, payload):
        self._require_config()
        configure_outbound_proxy()
        response = requests.post(
            f"https://graph.facebook.com/{self.config['graph_api_version']}/oauth/access_token",
            data=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def exchange_code(self, authorization_code):
        if not authorization_code: raise ValueError("authorization_code is required")
        short = self._token_exchange({"client_id": self.config["app_id"], "client_secret": self.config["app_secret"], "redirect_uri": self.config["redirect_uri"], "code": authorization_code})
        long = self._token_exchange({"grant_type": "fb_exchange_token", "client_id": self.config["app_id"], "client_secret": self.config["app_secret"], "fb_exchange_token": short.get("access_token")})
        if not long.get("access_token"): raise RuntimeError("Meta token exchange returned no access token")
        return {"access_token": long["access_token"], "refresh_token": None, "expires_at": None, "scopes": self.scopes}

    def discover_resources(self, access_token):
        data = self._get("me/accounts", access_token, fields="id,name,tasks,instagram_business_account").get("data", [])
        result = []
        for page in data:
            ig = page.get("instagram_business_account") or {}
            if self.platform == "instagram" and not ig.get("id"): continue
            result.append({"page_id": page.get("id"), "page_name": page.get("name"), "tasks": page.get("tasks") or [], "has_instagram_business_account": bool(ig.get("id")), "instagram_user_id": ig.get("id")})
        return result
