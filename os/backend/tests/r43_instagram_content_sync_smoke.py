from datetime import datetime, timedelta, timezone

import pytest

import integrations.instagram as module
from integrations.instagram import InstagramContentSync
from integrations.sync_planner import build_account_sync_plan
from integrations.sync_registry import get_content_sync_adapter

USER_TOKEN = "user-secret"
PAGE_TOKEN = "page-secret"


class Response:
    def __init__(self, payload, status=200):
        self._payload, self.status_code, self.ok = payload, status, status < 400

    def json(self):
        return self._payload


class Transport:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if url.endswith("/media"):
            return Response({"data": [
                {"id": "reel-1", "caption": "hello", "media_type": "VIDEO",
                 "media_product_type": "REELS", "permalink": "https://instagram.test/reel-1",
                 "timestamp": "2026-09-13T00:00:00+00:00"},
                {"id": "image-1", "media_type": "IMAGE", "media_product_type": "FEED",
                 "permalink": "https://instagram.test/image-1"},
                {"id": "carousel-1", "media_type": "CAROUSEL_ALBUM",
                 "media_product_type": "FEED", "permalink": "https://instagram.test/carousel-1"},
            ]})
        return Response({"id": "page-1", "access_token": PAGE_TOKEN})


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("OS_TESTING", "1")
    monkeypatch.setattr(module, "get_account", lambda _: {"id": 3, "platform": "instagram"})
    monkeypatch.setattr(module, "get_binding", lambda _: {"page_id": "page-1", "instagram_user_id": "ig-1"})
    monkeypatch.setattr(module, "get_token", lambda _: {"provider": "meta", "access_token": USER_TOKEN,
                                                         "scopes": ["pages_show_list", "instagram_basic"],
                                                         "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
    monkeypatch.setattr(module, "get_sync_state", lambda *_: {"content_cursor": None})
    monkeypatch.setattr(module, "mark_sync_started", lambda *args: None)
    monkeypatch.setattr(module, "mark_sync_success", lambda *args, **kwargs: {"content_status": "success"})
    monkeypatch.setattr(module, "mark_sync_failure", lambda *args: None)
    monkeypatch.setattr(module, "create_video_asset", lambda data: data)
    monkeypatch.setattr(module, "create_publish_task", lambda task: {"id": 1})
    monkeypatch.setattr(module, "update_publish_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "get_publish_tasks", lambda: [])


def test_registered_and_planned_without_analytics():
    assert get_content_sync_adapter("instagram") is not None
    plan = build_account_sync_plan(3, "instagram")
    assert plan["content_sync_registered"] is True
    assert plan["analytics_supported"] is False
    assert [item["operation"] for item in plan["operations"]] == ["content_sync"]


def test_reel_mapping_page_token_and_filtering(setup):
    transport = Transport()
    resolved = []
    sync = InstagramContentSync(transport=transport,
        page_token_resolver=lambda *args: (resolved.append(args) or PAGE_TOKEN))
    result = sync.sync(3, max_results=10)
    assert result["imported"] == 1
    assert result["skipped"] == 2
    assert resolved[0][2] == USER_TOKEN
    media_call = next(call for call in transport.calls if call[1].endswith("/media"))
    assert media_call[2]["headers"]["Authorization"] == f"Bearer {PAGE_TOKEN}"
    assert USER_TOKEN not in str(media_call)


def test_missing_account_fails_closed(monkeypatch):
    monkeypatch.setattr(module, "get_account", lambda _: None)
    with pytest.raises(RuntimeError, match="readiness"):
        InstagramContentSync().sync(3)


def test_cursor_and_full_refresh_are_bounded(setup, monkeypatch):
    transport = Transport()
    monkeypatch.setattr(module, "get_sync_state", lambda *_: {"content_cursor": "reel-1"})
    sync = InstagramContentSync(transport=transport, page_token_resolver=lambda *args: PAGE_TOKEN)
    assert sync.sync(3, sync_mode="incremental")["imported"] == 0
    assert sync.sync(3, sync_mode="full_refresh")["imported"] == 1
    assert len([c for c in transport.calls if c[1].endswith("/media")]) == 2


def test_error_redacts_tokens(setup):
    class Bad(Transport):
        def get(self, url, **kwargs):
            return Response({"error": {"message": "denied"}}, 403)
    sync = InstagramContentSync(transport=Bad(), page_token_resolver=lambda *args: PAGE_TOKEN)
    with pytest.raises(RuntimeError) as raised:
        sync.sync(3)
    assert USER_TOKEN not in str(raised.value)
    assert PAGE_TOKEN not in str(raised.value)
