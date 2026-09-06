from google.auth.transport.requests import AuthorizedSession

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
