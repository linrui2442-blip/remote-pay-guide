import os


def _normalize_proxy_url(value):
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None
    if "://" not in value:
        value = f"http://{value}"
    return value


def _parse_windows_proxy_server(raw):
    raw = str(raw or "").strip()
    if not raw:
        return None

    if "=" not in raw:
        proxy = _normalize_proxy_url(raw)
        return {"http": proxy, "https": proxy}

    parts = {}
    for item in raw.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key.strip().lower()] = _normalize_proxy_url(value)

    http_proxy = parts.get("http") or parts.get("https")
    https_proxy = parts.get("https") or parts.get("http")
    if not http_proxy and not https_proxy:
        return None
    return {"http": http_proxy, "https": https_proxy}


def _windows_user_proxy():
    if os.name != "nt":
        return None

    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        try:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not enabled:
                return None
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
        finally:
            winreg.CloseKey(key)
    except (OSError, ImportError):
        return None

    return _parse_windows_proxy_server(server)


def configure_outbound_proxy():
    """Make backend HTTP clients follow an enabled Windows user proxy.

    Browser OAuth can succeed while Python/httplib2 calls time out when a VPN
    exposes itself as a Windows user proxy. Respect explicit HTTP(S)_PROXY
    settings first; otherwise mirror the enabled Windows proxy into standard
    environment variables used by requests/google-auth/httplib2.
    """

    existing_http = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    existing_https = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if existing_http or existing_https:
        return {
            "source": "environment",
            "configured": True,
        }

    proxy = _windows_user_proxy()
    if not proxy:
        return {
            "source": "none",
            "configured": False,
        }

    if proxy.get("http"):
        os.environ["HTTP_PROXY"] = proxy["http"]
        os.environ["http_proxy"] = proxy["http"]
    if proxy.get("https"):
        os.environ["HTTPS_PROXY"] = proxy["https"]
        os.environ["https_proxy"] = proxy["https"]

    no_proxy = os.getenv("NO_PROXY") or os.getenv("no_proxy") or ""
    entries = [item.strip() for item in no_proxy.split(",") if item.strip()]
    for local in ("127.0.0.1", "localhost", "::1"):
        if local not in entries:
            entries.append(local)
    joined = ",".join(entries)
    os.environ["NO_PROXY"] = joined
    os.environ["no_proxy"] = joined

    return {
        "source": "windows_user_proxy",
        "configured": True,
    }
