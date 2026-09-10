"""Runtime-only Meta OAuth configuration."""
import os
from config.secure_store import SecureStoreError, get_secret

def _value(explicit, env_name, secret_name=None):
    if explicit: return explicit
    value = os.getenv(env_name)
    if value: return value
    if secret_name:
        try: return get_secret(secret_name)
        except SecureStoreError: pass
    return None

def meta_runtime_config(app_id=None, app_secret=None, redirect_uri=None, graph_api_version=None, facebook_login_config_id=None):
    return {"app_id": _value(app_id, "META_OAUTH_APP_ID", "meta_oauth_app_id"), "app_secret": _value(app_secret, "META_OAUTH_APP_SECRET", "meta_oauth_app_secret"), "redirect_uri": _value(redirect_uri, "META_OAUTH_REDIRECT_URI"), "facebook_redirect_uri": _value(None, "META_FACEBOOK_OAUTH_REDIRECT_URI"), "instagram_redirect_uri": _value(None, "META_INSTAGRAM_OAUTH_REDIRECT_URI"), "graph_api_version": _value(graph_api_version, "META_GRAPH_API_VERSION"), "facebook_login_config_id": _value(facebook_login_config_id, "META_FACEBOOK_LOGIN_CONFIG_ID")}

def meta_config_status():
    config = meta_runtime_config()
    missing = [key for key in ("app_id", "app_secret", "graph_api_version") if not config.get(key)]
    if not config.get("facebook_redirect_uri") and not config.get("redirect_uri"): missing.append("facebook_redirect_uri")
    if not config.get("instagram_redirect_uri") and not config.get("redirect_uri"): missing.append("instagram_redirect_uri")
    if not config.get("facebook_login_config_id"): missing.append("META_FACEBOOK_LOGIN_CONFIG_ID")
    return {"configured": not missing, "app_id_configured": bool(config["app_id"]), "facebook_login_configured": bool(config["facebook_login_config_id"]), "missing_configuration": missing, "redirect_uri": config["redirect_uri"], "facebook_redirect_uri": config["facebook_redirect_uri"] or config["redirect_uri"], "instagram_redirect_uri": config["instagram_redirect_uri"] or config["redirect_uri"], "graph_api_version": config["graph_api_version"]}
