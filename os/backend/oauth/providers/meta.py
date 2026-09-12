import secrets
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import requests
from config.network import configure_outbound_proxy
from oauth.manager import create_oauth_state
from oauth.meta_runtime_config import meta_runtime_config
from oauth.manager import get_token
from oauth.meta_bindings import get_binding
from accounts.manager import get_account

FACEBOOK_PUBLISH_SCOPES = ["pages_show_list", "pages_read_engagement", "pages_manage_posts"]
INSTAGRAM_PUBLISH_SCOPES = ["pages_show_list", "pages_read_engagement", "instagram_basic", "instagram_content_publish"]
META_FULL_SCOPES = sorted(set(FACEBOOK_PUBLISH_SCOPES + INSTAGRAM_PUBLISH_SCOPES))

class MetaOAuthConfigurationError(RuntimeError):
    pass

class MetaOAuthRequestError(RuntimeError):
    def __init__(self, status, error_type=None, code=None, subcode=None, message=None, fbtrace_id=None):
        safe_message = str(message or "Meta OAuth request failed").replace("access_token", "credential").replace("client_secret", "credential").replace("authorization_code", "credential")
        safe_message = re.sub(r"(?i)bearer\s+\S+", "[REDACTED_CREDENTIAL]", safe_message)
        safe_message = re.sub(r"\b[A-Z][A-Z0-9_]*(?:TOKEN|SECRET)\b", "[REDACTED_CREDENTIAL]", safe_message)
        fields = [f"HTTP {status}", f"type={error_type or 'unknown'}", f"code={code if code is not None else 'unknown'}"]
        if subcode is not None: fields.append(f"subcode={subcode}")
        fields.append(f"message={safe_message}")
        if fbtrace_id: fields.append(f"fbtrace_id={fbtrace_id}")
        super().__init__("; ".join(fields))

class MetaOAuthProvider:
    def __init__(self, platform="facebook", **config):
        self.platform = platform.strip().lower()
        if self.platform not in {"facebook", "instagram"}: raise ValueError("unsupported Meta platform")
        self.scope_profile = config.pop("scope_profile", None)
        self.config = meta_runtime_config(**config)
        self.scope_profile = self.scope_profile or ("facebook_publish" if self.platform == "facebook" else "instagram_publish")
        self.scopes = self._scopes()

    @property
    def redirect_uri(self):
        return self.config.get(f"{self.platform}_redirect_uri") or self.config.get("redirect_uri")

    def _scopes(self):
        if self.scope_profile == "facebook_publish": return list(FACEBOOK_PUBLISH_SCOPES)
        if self.scope_profile == "instagram_publish": return list(INSTAGRAM_PUBLISH_SCOPES)
        if self.scope_profile == "meta_full": return list(META_FULL_SCOPES)
        raise ValueError("unsupported Meta scope profile")

    def _require_config(self):
        missing = [key for key in ("app_id", "app_secret", "graph_api_version") if not self.config.get(key)]
        if not self.redirect_uri: missing.append(f"{self.platform}_redirect_uri")
        if not self.config.get("facebook_login_config_id"): missing.append("META_FACEBOOK_LOGIN_CONFIG_ID")
        if missing: raise MetaOAuthConfigurationError("missing Meta OAuth configuration: " + ", ".join(missing))

    def authorization_url(self, account_id):
        self._require_config(); state = secrets.token_urlsafe(32)
        create_oauth_state(account_id, state, provider="meta", connector_platform=self.platform, scope_profile=self.scope_profile)
        query = {"client_id": self.config["app_id"], "redirect_uri": self.redirect_uri, "state": state, "scope": ",".join(self.scopes), "response_type": "code", "config_id": self.config["facebook_login_config_id"], "override_default_response_type": "true"}
        return {"authorization_url": "https://www.facebook.com/" + self.config["graph_api_version"] + "/dialog/oauth?" + urlencode(query), "state": state, "scope_profile": self.scope_profile, "scopes": self.scopes}

    def _get(self, resource, access_token, **params):
        self._require_config()
        configure_outbound_proxy()
        response = requests.get(f"https://graph.facebook.com/{self.config['graph_api_version']}/{resource}", params=params, headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
        response.raise_for_status(); return response.json()

    def _token_exchange(self, payload):
        self._require_config()
        configure_outbound_proxy()
        response = requests.get(
            f"https://graph.facebook.com/{self.config['graph_api_version']}/oauth/access_token",
            params=payload,
            timeout=30,
        )
        if not response.ok:
            try: error = (response.json() or {}).get("error") or {}
            except Exception: error = {}
            raise MetaOAuthRequestError(response.status_code, error.get("type"), error.get("code"), error.get("error_subcode"), error.get("message"), error.get("fbtrace_id"))
        return response.json()

    def exchange_code(self, authorization_code):
        if not authorization_code: raise ValueError("authorization_code is required")
        short = self._token_exchange({"client_id": self.config["app_id"], "client_secret": self.config["app_secret"], "redirect_uri": self.redirect_uri, "code": authorization_code})
        long = self._token_exchange({"grant_type": "fb_exchange_token", "client_id": self.config["app_id"], "client_secret": self.config["app_secret"], "fb_exchange_token": short.get("access_token")})
        if not long.get("access_token"): raise RuntimeError("Meta token exchange returned no access token")
        permission_data = self._get("me/permissions", long["access_token"]).get("data", [])
        granted = sorted({item.get("permission") for item in permission_data if item.get("status") == "granted" and item.get("permission")})
        expires_at = None
        if long.get("expires_in") is not None:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(long["expires_in"]))).isoformat()
        return {"access_token": long["access_token"], "refresh_token": None, "expires_at": expires_at, "scopes": granted}

    def discover_resources(self, access_token):
        data = self._get("me/accounts", access_token, fields="id,name,tasks,instagram_business_account").get("data", [])
        result = []
        for page in data:
            ig = page.get("instagram_business_account") or {}
            if self.platform == "instagram" and not ig.get("id"): continue
            result.append({"page_id": page.get("id"), "page_name": page.get("name"), "tasks": page.get("tasks") or [], "has_instagram_business_account": bool(ig.get("id")), "instagram_user_id": ig.get("id")})
        return result

    def resolve_page_access_token(self, account_id, bound_page_id, access_token=None, transport=None):
        """Resolve a bound Page credential in memory for one live operation."""
        account = get_account(account_id)
        binding = get_binding(account_id)
        token = {"access_token": access_token} if access_token else get_token(account_id)
        if not account or str(account.get("platform", "")).lower() not in {"facebook", "instagram"}:
            raise MetaOAuthConfigurationError("Meta account is missing")
        if not binding or not bound_page_id or str(binding.get("page_id")) != str(bound_page_id):
            raise MetaOAuthConfigurationError("Meta binding page identity is invalid")
        if not token or not token.get("access_token"):
            raise MetaOAuthConfigurationError("Meta user credential is missing")
        scopes = token.get("scopes") or []
        if isinstance(scopes, str):
            try: scopes = json.loads(scopes)
            except Exception: scopes = scopes.split()
        required = set(INSTAGRAM_PUBLISH_SCOPES if str(account.get("platform", "")).lower() == "instagram" else FACEBOOK_PUBLISH_SCOPES)
        if not required.issubset(set(scopes)):
            raise MetaOAuthConfigurationError("Meta user credential lacks page publishing scope metadata")
        if token.get("expires_at"):
            try:
                expiry = datetime.fromisoformat(str(token["expires_at"]).replace("Z", "+00:00"))
                if expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= datetime.now(timezone.utc): raise MetaOAuthConfigurationError("Meta user credential is expired")
            except ValueError: raise MetaOAuthConfigurationError("Meta user credential expiry is invalid")
        http = transport or requests
        try:
            response = http.get(
                f"https://graph.facebook.com/{self.config.get('graph_api_version') or 'v26.0'}/{bound_page_id}",
                params={"fields": "id,access_token"},
                headers={"Authorization": f"Bearer {token['access_token']}"}, timeout=30,
            )
            if not response.ok:
                try: error = (response.json() or {}).get("error") or {}
                except Exception: error = {}
                raise MetaOAuthRequestError(response.status_code, error.get("type"), error.get("code"), error.get("error_subcode"), error.get("message"), error.get("fbtrace_id"))
            payload = response.json() or {}
        except MetaOAuthRequestError:
            raise
        except Exception as exc:
            raise MetaOAuthConfigurationError("Meta page credential resolution failed") from None
        if str(payload.get("id")) != str(bound_page_id):
            raise MetaOAuthConfigurationError("Meta page credential response identity mismatch")
        if not payload.get("access_token"):
            raise MetaOAuthConfigurationError("Meta page credential response was missing access token")
        return payload["access_token"]
