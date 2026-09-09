"""Network-free contract checks for the official YouTube upload transport."""

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from integrations import google_transport
from publish.adapters.youtube_api import _safe_upload_error


class Credentials:
    pass


def _explicit_proxy(http):
    info = http.proxy_info
    return None if callable(info) else info


def main():
    original = google_transport.get_active_proxy_map
    try:
        google_transport.get_active_proxy_map = lambda: {}
        no_proxy = google_transport.build_authorized_httplib2(Credentials())
        assert _explicit_proxy(no_proxy.http) is None

        google_transport.get_active_proxy_map = lambda: {
            "http": "http://127.0.0.1:12345",
            "https": "http://127.0.0.1:12345",
        }
        manual = google_transport.build_authorized_httplib2(Credentials())
        info = manual.http.proxy_info
        assert info.proxy_host == "127.0.0.1"
        assert info.proxy_port == 12345
        assert info.proxy_type == getattr(getattr(google_transport.httplib2, "socks", None), "PROXY_TYPE_HTTP", 3)

        google_transport.get_active_proxy_map = lambda: {}
        disabled = google_transport.build_authorized_httplib2(Credentials())
        assert _explicit_proxy(disabled.http) is None

        error = OSError(10060, "Authorization Bearer secret upload_id=abc https://upload.example/session")
        safe = _safe_upload_error(error)
        assert ("os_error" in safe or "timeout" in safe) and "errno=10060" in safe
        for secret in ("Authorization", "Bearer", "secret", "upload_id", "upload.example"):
            assert secret not in safe
        print("YouTube upload transport smoke test passed")
        print("no proxy; manual HTTP proxy; disabled mode; safe retry diagnostics")
    finally:
        google_transport.get_active_proxy_map = original


if __name__ == "__main__":
    main()
