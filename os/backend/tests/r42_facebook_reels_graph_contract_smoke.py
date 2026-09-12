"""Network-free Facebook Reels adapter and Page-token contract."""
from datetime import datetime, timedelta, timezone
import pytest
from publish.adapters import facebook as module
from publish.adapters.facebook import FacebookAdapter

USER = "USER_SECRET_TOKEN"
PAGE = "PAGE_SECRET_TOKEN"

class Response:
    def __init__(self, payload, status=200): self.payload, self.status_code, self.ok = payload, status, status < 400
    def json(self): return self.payload
    def raise_for_status(self):
        if not self.ok: raise RuntimeError(f"HTTP {self.status_code}")

class Transport:
    def __init__(self, responses): self.responses, self.calls = list(responses), []
    def post(self, url, **kwargs): self.calls.append(("POST", url, kwargs)); return Response(self.responses.pop(0))
    def get(self, url, **kwargs): self.calls.append(("GET", url, kwargs)); return Response(self.responses.pop(0))

def ready(monkeypatch, *, account=True, binding=True, token=True, scopes=None, expires_at=None):
    monkeypatch.setattr(module, "get_account", lambda _: {"platform": "facebook"} if account else None)
    monkeypatch.setattr(module, "get_binding", lambda _: {"platform": "facebook", "page_id": "page-1"} if binding else None)
    row = {"provider": "facebook", "access_token": USER, "scopes": scopes or module.FACEBOOK_PUBLISH_SCOPES, "expires_at": expires_at}
    monkeypatch.setattr(module, "get_token", lambda _: row if token else None)
    monkeypatch.setattr(module, "resolve_page_access_token", lambda *args: PAGE)

def test_default_gate_is_closed(monkeypatch):
    monkeypatch.delenv("META_FACEBOOK_LIVE_PUBLISH_ENABLED", raising=False)
    status = FacebookAdapter().get_status()
    assert status["implementation_ready"] and not status["configuration_ready"] and not status["publish_ready"]

@pytest.mark.parametrize("kwargs", [{"account": False}, {"binding": False}, {"token": False}, {"scopes": ["pages_show_list"]}, {"expires_at": (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()}])
def test_readiness_fail_closed(monkeypatch, kwargs):
    ready(monkeypatch, **kwargs)
    assert FacebookAdapter().get_account_readiness(3)["ready"] is False

def test_readiness_is_network_free(monkeypatch):
    ready(monkeypatch); calls=[]
    monkeypatch.setattr(module, "resolve_page_access_token", lambda *args: calls.append(args))
    adapter = FacebookAdapter(); assert adapter.get_account_readiness(3)["ready"] is True; assert calls == []

def test_public_asset_and_create_upload_finish_use_page_token(monkeypatch):
    ready(monkeypatch)
    transport = Transport([{"video_id":"fb-video-1","upload_url":"https://rupload.facebook.test/video"}, {"status":"CREATED"}, {"success": True}, {"success": True}])
    events=[]
    result = FacebookAdapter(transport=transport, live_publish_enabled=True).publish_reel_via_graph({"asset_url":"https://linrui2442-blip.github.io/remote-pay-guide/media/test-facebook.mp4"}, 3, title="T", description="D", transport=transport, operation_callback=lambda *x: events.append(x))
    assert result["video_id"] == "fb-video-1" and result["provider_operation_status"] == "PUBLISHED"
    assert [x[0] for x in transport.calls] == ["POST", "GET", "POST", "POST"]
    assert transport.calls[0][2]["headers"]["Authorization"] == f"OAuth {PAGE}"
    assert transport.calls[2][2]["headers"]["file_url"].endswith("test-facebook.mp4")
    assert events == [("fb-video-1","CREATED"),("fb-video-1","UPLOADED"),("fb-video-1","PUBLISHED")]

def test_local_asset_rejected_before_external_write(monkeypatch):
    ready(monkeypatch); transport=Transport([])
    with pytest.raises(ValueError, match="public http"):
        FacebookAdapter(transport=transport, live_publish_enabled=True).publish_reel_via_graph({"file_path":"C:/private/x.mp4"}, 3, transport=transport)
    assert transport.calls == []

def test_published_retry_has_zero_writes(monkeypatch):
    ready(monkeypatch); transport=Transport([])
    result=FacebookAdapter(transport=transport, live_publish_enabled=True).publish_reel_via_graph({"asset_url":"https://example.test/x.mp4"},3,transport=transport,provider_operation_id="fb-video-1",provider_operation_status="PUBLISHED")
    assert result["status"]=="published" and transport.calls==[]

def test_uploaded_retry_skips_create_and_upload(monkeypatch):
    ready(monkeypatch); transport=Transport([{"success":True}])
    result=FacebookAdapter(transport=transport, live_publish_enabled=True).publish_reel_via_graph({"asset_url":"https://example.test/x.mp4"},3,transport=transport,provider_operation_id="fb-video-1",provider_operation_status="UPLOADED")
    assert result["status"]=="published" and len(transport.calls)==1 and transport.calls[0][2]["params"]["upload_phase"]=="finish"

def test_ambiguous_remote_state_fails_closed(monkeypatch):
    ready(monkeypatch); transport=Transport([{"video_id":"fb-video-1","upload_url":"https://rupload.test/x"},{"status":"UNKNOWN"}])
    with pytest.raises(RuntimeError, match="ambiguous"):
        FacebookAdapter(transport=transport, live_publish_enabled=True).publish_reel_via_graph({"asset_url":"https://example.test/x.mp4"},3,transport=transport)

def test_errors_redact_both_credentials(monkeypatch):
    ready(monkeypatch); transport=Transport([{"video_id":"fb-video-1","upload_url":"https://rupload.test/x"}]); transport.post=lambda url,**kwargs: (_ for _ in ()).throw(RuntimeError(USER+PAGE))
    with pytest.raises(RuntimeError) as raised: FacebookAdapter(transport=transport, live_publish_enabled=True).publish_reel_via_graph({"asset_url":"https://example.test/x.mp4"},3,transport=transport)
    assert USER not in str(raised.value) and PAGE not in str(raised.value)
