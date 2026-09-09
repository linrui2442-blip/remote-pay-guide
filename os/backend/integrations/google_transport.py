from google.auth.transport.requests import AuthorizedSession
from google_auth_httplib2 import AuthorizedHttp
import httplib2
from urllib.parse import urlparse

from config.network import configure_outbound_proxy


def get_active_proxy_map():
    """Return the exact proxy map currently selected by Remote Pay Guide OS.

    `configure_outbound_proxy` reapplies the persisted OS preference first, so
    manual mode does not depend on whether a Google client library chooses to
    honor process environment variables on its own.
    """
    configure_outbound_proxy()

    import os

    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")

    proxies = {}
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy
    elif http_proxy:
        proxies["https"] = http_proxy
    if "http" not in proxies and https_proxy:
        proxies["http"] = https_proxy
    return proxies


def build_authorized_session(credentials, session_factory=AuthorizedSession):
    """Create a Google-auth requests session with the OS proxy applied directly."""
    session = session_factory(credentials)
    proxies = get_active_proxy_map()
    if proxies:
        session.proxies.update(proxies)
    return session


def build_authorized_httplib2(credentials):
    """Create an authorized httplib2 transport using the OS proxy choice."""
    proxies = get_active_proxy_map()
    proxy_url = proxies.get("https") or proxies.get("http")
    if proxy_url:
        parsed = urlparse(proxy_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("OS proxy must be an HTTP(S) proxy for Google uploads")
        # httplib2 exposes the socks constants only when optional SOCKS
        # support is installed; HTTP proxy support itself does not require it.
        proxy_type_http = getattr(getattr(httplib2, "socks", None), "PROXY_TYPE_HTTP", 3)
        proxy_info = httplib2.ProxyInfo(
            proxy_type_http,
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            proxy_user=parsed.username,
            proxy_pass=parsed.password,
        )
        http = httplib2.Http(proxy_info=proxy_info)
    else:
        http = httplib2.Http()
    return AuthorizedHttp(credentials, http=http)
