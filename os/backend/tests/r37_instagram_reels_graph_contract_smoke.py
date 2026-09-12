"""Network-free Instagram Reels readiness and container contract checks."""
from datetime import datetime, timedelta, timezone
from publish.adapters import instagram as module
from publish.adapters.instagram import InstagramAdapter


class Response:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): return None
    def json(self): return self.payload


class FakeTransport:
    def __init__(self, responses): self.responses, self.calls = list(responses), []
    def post(self, url, **kwargs): self.calls.append(("POST", url, kwargs)); return Response(self.responses.pop(0))
    def get(self, url, **kwargs): self.calls.append(("GET", url, kwargs)); return Response(self.responses.pop(0))


def token(**overrides):
    value = {"provider": "meta", "access_token": "fake-token", "scopes": ["pages_show_list", "pages_read_engagement", "instagram_basic", "instagram_content_publish"], "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
    value.update(overrides)
    return value


def ready(monkeypatch, value=None, binding=None):
    monkeypatch.setattr(module, "get_account", lambda _: {"id": 3, "platform": "instagram"})
    monkeypatch.setattr(module, "get_binding", lambda _: binding or {"platform": "instagram", "instagram_user_id": "ig-3"})
    monkeypatch.setattr(module, "get_token", lambda _: value or token())


def test_readiness_fail_closed(monkeypatch):
    adapter = InstagramAdapter()
    ready(monkeypatch, token(access_token=None)); assert not adapter.get_account_readiness(3)["ready"]
    ready(monkeypatch, binding={"platform": "facebook", "instagram_user_id": "ig-3"}); assert not adapter.get_account_readiness(3)["ready"]
    ready(monkeypatch, token(scopes=["pages_show_list"])); assert not adapter.get_account_readiness(3)["ready"]
    ready(monkeypatch, token(expires_at="2000-01-01T00:00:00+00:00")); assert not adapter.get_account_readiness(3)["ready"]


def test_polling_order_and_terminal_states(monkeypatch):
    ready(monkeypatch)
    fake = FakeTransport([{"id": "creation-1"}, {"status_code": "IN_PROGRESS", "status": "IN_PROGRESS"}, {"status_code": "FINISHED", "status": "FINISHED"}, {"id": "media-1"}])
    result = InstagramAdapter(transport=fake).publish_reel_via_graph({"asset_url": "https://example.test/reel.mp4"}, 3, sleep_fn=lambda _: None, max_attempts=3)
    assert result["video_id"] == "media-1"
    assert [call[0] for call in fake.calls] == ["POST", "GET", "GET", "POST"]


def test_terminal_states_and_timeout_never_publish(monkeypatch):
    ready(monkeypatch)
    for state in ("ERROR", "EXPIRED", "PUBLISHED"):
        fake = FakeTransport([{"id": "creation-1"}, {"status_code": state, "status": state}])
        try: InstagramAdapter(transport=fake).publish_reel_via_graph({"asset_url": "https://example.test/reel.mp4"}, 3, sleep_fn=lambda _: None)
        except RuntimeError: pass
        assert not any(call[1].endswith("media_publish") for call in fake.calls)
    fake = FakeTransport([{"id": "creation-1"}, {"status_code": "IN_PROGRESS", "status": "IN_PROGRESS"}])
    try: InstagramAdapter(transport=fake).publish_reel_via_graph({"asset_url": "https://example.test/reel.mp4"}, 3, sleep_fn=lambda _: None, max_attempts=1)
    except RuntimeError: pass
    assert not any(call[1].endswith("media_publish") for call in fake.calls)


def test_url_gate_and_publish_response_validation(monkeypatch):
    ready(monkeypatch)
    try: InstagramAdapter._video_url({"asset_url": "C:/private/reel.mp4"})
    except ValueError: pass
    else: raise AssertionError("private path accepted")


def test_missing_media_id_and_http_error_are_safe(monkeypatch):
    ready(monkeypatch)
    fake = FakeTransport([{"id": "creation-1"}, {"status_code": "FINISHED"}, {}])
    try:
        InstagramAdapter(transport=fake).publish_reel_via_graph({"asset_url": "https://example.test/reel.mp4"}, 3, sleep_fn=lambda _: None)
    except RuntimeError as exc:
        assert "media id" in str(exc)
    else:
        raise AssertionError("missing media id must fail closed")

    class FailingTransport(FakeTransport):
        def post(self, url, **kwargs):
            raise RuntimeError("Bearer SUPER_SECRET_FAKE_META_TOKEN Authorization access_token=SUPER_SECRET_FAKE_META_TOKEN")

    try:
        InstagramAdapter(transport=FailingTransport([])).publish_reel_via_graph({"asset_url": "https://example.test/reel.mp4"}, 3)
    except RuntimeError as exc:
        assert "SUPER_SECRET_FAKE_META_TOKEN" not in str(exc)
        assert "Authorization" not in str(exc)
        assert "[REDACTED_CREDENTIAL]" in str(exc)
    else:
        raise AssertionError("HTTP failure must fail closed")


def test_create_status_and_publish_errors_redact_runtime_token(monkeypatch):
    ready(monkeypatch, token(access_token="runtime-token"))
    class FailingTransport(FakeTransport):
        def __init__(self, fail_on):
            super().__init__([{"id": "creation-1"}, {"status_code": "FINISHED"}, {"id": "media-1"}])
            self.fail_on = fail_on
        def post(self, url, **kwargs):
            if self.fail_on == "create" or (self.fail_on == "publish" and url.endswith("media_publish")):
                raise RuntimeError("Bearer runtime-token Authorization access_token=runtime-token")
            return super().post(url, **kwargs)
        def get(self, url, **kwargs):
            if self.fail_on == "status":
                raise RuntimeError("Bearer runtime-token Authorization access_token=runtime-token")
            return super().get(url, **kwargs)
    for failure in ("create", "status", "publish"):
        try:
            InstagramAdapter(transport=FailingTransport(failure)).publish_reel_via_graph(
                {"asset_url": "https://example.test/reel.mp4"}, 3, sleep_fn=lambda _: None
            )
        except RuntimeError as exc:
            assert "runtime-token" not in str(exc)
            assert "Authorization" not in str(exc)
        else:
            raise AssertionError(f"{failure} failure must fail closed")
