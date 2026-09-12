"""Network-free Meta Page credential boundary tests."""

from datetime import datetime, timedelta, timezone

import pytest
from oauth.providers import meta as meta_module
from oauth.providers.meta import MetaOAuthProvider, MetaOAuthRequestError
from publish.adapters import instagram as instagram_module
from publish.adapters.instagram import InstagramAdapter


USER_SECRET_TOKEN = "USER_SECRET_TOKEN"
PAGE_SECRET_TOKEN = "PAGE_SECRET_TOKEN"


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status_code, self.ok = payload, status, status < 400

    def json(self):
        return self.payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


class Transport:
    def __init__(self, payload, status=200):
        self.payload, self.status, self.calls = payload, status, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.payload, self.status)


def ready_metadata(monkeypatch, *, account=True, binding=True, token=True, scopes=None, expires_at=None):
    monkeypatch.setattr(meta_module, "get_account", lambda _: {"platform": "instagram"} if account else None)
    monkeypatch.setattr(meta_module, "get_binding", lambda _: {"platform": "instagram", "page_id": "page-1"} if binding else None)
    row = {"access_token": USER_SECRET_TOKEN, "scopes": scopes or ["pages_show_list", "pages_read_engagement", "instagram_basic", "instagram_content_publish"], "expires_at": expires_at}
    monkeypatch.setattr(meta_module, "get_token", lambda _: row if token else None)


def test_resolver_uses_bound_page_and_returns_page_token(monkeypatch):
    ready_metadata(monkeypatch)
    transport = Transport({"id": "page-1", "access_token": PAGE_SECRET_TOKEN})
    result = MetaOAuthProvider(platform="instagram").resolve_page_access_token(3, "page-1", transport=transport)
    assert result == PAGE_SECRET_TOKEN
    assert transport.calls[0][0].endswith("/v26.0/page-1")
    assert transport.calls[0][1]["headers"]["Authorization"] == f"Bearer {USER_SECRET_TOKEN}"


@pytest.mark.parametrize("payload", [{"id": "other", "access_token": PAGE_SECRET_TOKEN}, {"id": "page-1"}])
def test_resolver_fails_closed_on_bad_page_response(monkeypatch, payload):
    ready_metadata(monkeypatch)
    with pytest.raises(Exception):
        MetaOAuthProvider(platform="instagram").resolve_page_access_token(3, "page-1", transport=Transport(payload))


def test_resolver_missing_token_scope_or_expiry_fails_closed(monkeypatch):
    for kwargs in ({"token": False}, {"scopes": ["instagram_basic"]}, {"expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}):
        ready_metadata(monkeypatch, **kwargs)
        with pytest.raises(Exception):
            MetaOAuthProvider(platform="instagram").resolve_page_access_token(3, "page-1", transport=Transport({"id": "page-1", "access_token": PAGE_SECRET_TOKEN}))


def test_meta_error_redacts_user_and_page_tokens(monkeypatch):
    ready_metadata(monkeypatch)
    transport = Transport({"error": {"type": "OAuthException", "code": 190, "message": USER_SECRET_TOKEN + PAGE_SECRET_TOKEN}}, status=403)
    with pytest.raises(MetaOAuthRequestError) as raised:
        MetaOAuthProvider(platform="instagram").resolve_page_access_token(3, "page-1", transport=transport)
    text = str(raised.value)
    assert USER_SECRET_TOKEN not in text and PAGE_SECRET_TOKEN not in text
    assert "code=190" in text


def test_instagram_graph_publish_uses_resolved_page_token(monkeypatch):
    monkeypatch.setattr(instagram_module, "get_account", lambda _: {"platform": "instagram"})
    monkeypatch.setattr(instagram_module, "get_binding", lambda _: {"platform": "instagram", "page_id": "page-1", "instagram_user_id": "ig-1"})
    monkeypatch.setattr(instagram_module, "get_token", lambda _: {"provider": "instagram", "access_token": USER_SECRET_TOKEN, "scopes": ["pages_show_list", "pages_read_engagement", "instagram_basic", "instagram_content_publish"]})
    monkeypatch.setattr(instagram_module, "resolve_page_access_token", lambda account_id, page_id, user, transport: PAGE_SECRET_TOKEN)
    transport = Transport({"id": "creation-1"})
    transport.post = lambda url, **kwargs: (transport.calls.append((url, kwargs)) or Response({"id": "creation-1"}))
    transport.get = lambda url, **kwargs: (transport.calls.append((url, kwargs)) or Response({"status_code": "FINISHED"}))
    result = InstagramAdapter(transport=transport, live_publish_enabled=True).publish_reel_via_graph({"asset_url": "https://example.test/x.mp4"}, 3, sleep_fn=lambda _: None)
    assert result["status"] == "published"
    assert all(call[1]["headers"]["Authorization"] == f"Bearer {PAGE_SECRET_TOKEN}" for call in transport.calls)


def test_resource_representation_never_contains_page_token():
    provider = MetaOAuthProvider(platform="instagram")
    provider._get = lambda *args, **kwargs: {"data": [{"id": "page-1", "name": "Page", "instagram_business_account": {"id": "ig-1"}}]}
    resources = provider.discover_resources(USER_SECRET_TOKEN)
    assert PAGE_SECRET_TOKEN not in str(resources)
    assert all("access_token" not in item for item in resources)
