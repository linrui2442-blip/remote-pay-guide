import os
import sqlite3
from datetime import datetime

DB_PATH = "os/database/os.db"


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


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS network_proxy_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            mode TEXT NOT NULL,
            proxy_url TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def get_proxy_settings():
    _init_db()
    conn = _connect()
    row = conn.execute(
        "SELECT mode, proxy_url, updated_at FROM network_proxy_settings WHERE id=1"
    ).fetchone()
    conn.close()
    if not row:
        return {"mode": "system", "proxy_url": None, "updated_at": None}
    return dict(row)


def _ensure_local_no_proxy():
    no_proxy = os.getenv("NO_PROXY") or os.getenv("no_proxy") or ""
    entries = [item.strip() for item in no_proxy.split(",") if item.strip()]
    for local in ("127.0.0.1", "localhost", "::1"):
        if local not in entries:
            entries.append(local)
    joined = ",".join(entries)
    os.environ["NO_PROXY"] = joined
    os.environ["no_proxy"] = joined


def _clear_proxy_environment():
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(name, None)
    _ensure_local_no_proxy()


def _apply_proxy(proxy_url):
    normalized = _normalize_proxy_url(proxy_url)
    if not normalized:
        raise ValueError("proxy_url is required for manual proxy mode")
    os.environ["HTTP_PROXY"] = normalized
    os.environ["http_proxy"] = normalized
    os.environ["HTTPS_PROXY"] = normalized
    os.environ["https_proxy"] = normalized
    _ensure_local_no_proxy()
    return normalized


def save_proxy_settings(mode="system", proxy_url=None):
    normalized_mode = str(mode or "system").strip().lower()
    if normalized_mode not in {"system", "manual", "disabled"}:
        raise ValueError("mode must be one of: system, manual, disabled")

    normalized_proxy = _normalize_proxy_url(proxy_url) if normalized_mode == "manual" else None
    if normalized_mode == "manual" and not normalized_proxy:
        raise ValueError("proxy_url is required for manual proxy mode")

    _init_db()
    now = datetime.utcnow().isoformat()
    conn = _connect()
    conn.execute(
        """
        INSERT INTO network_proxy_settings (id, mode, proxy_url, updated_at)
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            mode=excluded.mode,
            proxy_url=excluded.proxy_url,
            updated_at=excluded.updated_at
        """,
        (normalized_mode, normalized_proxy, now),
    )
    conn.commit()
    conn.close()

    runtime = configure_outbound_proxy()
    return {**get_proxy_settings(), "runtime": runtime}


def configure_outbound_proxy():
    """Apply the OS proxy preference to outbound HTTP clients.

    The persisted OS setting has priority. Manual mode uses the exact proxy
    chosen in the Remote Pay Guide OS UI. System mode keeps the previous
    behavior: explicit process environment first, then the Windows user proxy.
    Disabled mode clears HTTP(S) proxy variables for this backend process.
    """

    settings = get_proxy_settings()
    mode = settings.get("mode") or "system"

    if mode == "manual":
        _clear_proxy_environment()
        proxy_url = _apply_proxy(settings.get("proxy_url"))
        return {
            "source": "os_manual",
            "configured": True,
            "proxy_url": proxy_url,
        }

    if mode == "disabled":
        _clear_proxy_environment()
        return {
            "source": "disabled",
            "configured": False,
            "proxy_url": None,
        }

    existing_http = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    existing_https = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if existing_http or existing_https:
        _ensure_local_no_proxy()
        return {
            "source": "environment",
            "configured": True,
            "proxy_url": existing_https or existing_http,
        }

    proxy = _windows_user_proxy()
    if not proxy:
        _ensure_local_no_proxy()
        return {
            "source": "none",
            "configured": False,
            "proxy_url": None,
        }

    if proxy.get("http"):
        os.environ["HTTP_PROXY"] = proxy["http"]
        os.environ["http_proxy"] = proxy["http"]
    if proxy.get("https"):
        os.environ["HTTPS_PROXY"] = proxy["https"]
        os.environ["https_proxy"] = proxy["https"]
    _ensure_local_no_proxy()

    return {
        "source": "windows_user_proxy",
        "configured": True,
        "proxy_url": proxy.get("https") or proxy.get("http"),
    }


def get_proxy_status():
    settings = get_proxy_settings()
    effective = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    return {
        **settings,
        "effective_proxy": effective,
        "runtime_configured": bool(effective),
    }
