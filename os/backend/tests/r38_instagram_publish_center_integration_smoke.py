"""Network-free end-to-end Publish Center contracts for Instagram."""
from datetime import datetime, timedelta, timezone
import os
import pytest
import publish.manager as pm
import publish.orchestrator as orch
import publish.worker as worker_module
import publish.adapters.instagram as instagram_module
from publish.adapters.instagram import InstagramAdapter
from publish.models import PublishTask
from publish.queue import PublishQueue
from publish.registry import register_adapter

TOKEN = "SUPER_SECRET_FAKE_META_TOKEN"

class Response:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): return None
    def json(self): return self.payload

class FakeTransport:
    def __init__(self, states=("FINISHED",), fail_at=None): self.states=list(states); self.fail_at=fail_at; self.calls=[]
    def _response(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        if self.fail_at == len(self.calls): raise RuntimeError(f"Bearer {TOKEN} Authorization access_token={TOKEN}")
        if method == "POST" and url.endswith("/media"): return Response({"id":"creation-1"})
        if method == "GET":
            state=self.states.pop(0) if self.states else "FINISHED"
            return Response({"status_code":state,"status":state})
        return Response({"id":"media-1"})
    def post(self, url, **kwargs): return self._response("POST", url, kwargs)
    def get(self, url, **kwargs): return self._response("GET", url, kwargs)

@pytest.fixture
def isolated(monkeypatch):
    pm._init_db(); conn=pm._connect(); conn.execute("DELETE FROM publish_tasks"); conn.commit(); conn.close()
    account={"id":3,"platform":"instagram","status":"connected"}; binding={"platform":"instagram","instagram_user_id":"ig-3"}
    token={"provider":"instagram","access_token":TOKEN,"scopes":["pages_show_list","pages_read_engagement","instagram_basic","instagram_content_publish"],"expires_at":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
    asset={"asset_id":"asset-1","video_id":"video-1","status":"ready","asset_url":"https://example.test/reel.mp4","file_path":None,"location":"https://example.test/reel.mp4"}
    monkeypatch.setattr(orch,"get_account",lambda _:account); monkeypatch.setattr(orch,"get_asset_by_asset_id",lambda _:asset); monkeypatch.setattr(orch,"get_asset",lambda _:asset)
    monkeypatch.setattr(worker_module,"get_asset_by_asset_id",lambda _:asset); monkeypatch.setattr(worker_module,"get_asset",lambda _:asset)
    monkeypatch.setattr(instagram_module,"get_account",lambda _:account); monkeypatch.setattr(instagram_module,"get_binding",lambda _:binding); monkeypatch.setattr(instagram_module,"get_token",lambda _:token)
    return account,binding,token,asset

def install(monkeypatch, transport):
    adapter=InstagramAdapter(transport=transport,live_publish_enabled=True); register_adapter("instagram",adapter,replace=True); monkeypatch.setattr(orch,"get_adapter",lambda platform: adapter if platform=="instagram" else None); return adapter

def task(**kwargs):
    values={"platform":"instagram","account_id":3,"asset_id":"asset-1","title":"Title","description":"Description"}; values.update(kwargs); return PublishTask(**values)

def test_default_production_gate_is_closed(): assert InstagramAdapter().get_status()["publish_ready"] is False

def test_local_only_instagram_asset_rejected_before_task_creation(monkeypatch,isolated):
    asset=isolated[3].copy(); asset.update(asset_url=None,location="C:/private/reel.mp4",file_path="C:/private/reel.mp4"); monkeypatch.setattr(orch,"get_asset_by_asset_id",lambda _:asset)
    fake=FakeTransport(); install(monkeypatch,fake)
    with pytest.raises(Exception,match="public http"): orch.prepare_publish_task(task())
    assert pm.get_publish_tasks()==[] and fake.calls==[]

def test_prepare_public_asset_makes_zero_graph_calls(monkeypatch,isolated):
    fake=FakeTransport(); install(monkeypatch,fake); result=orch.prepare_publish_task(task()); assert result["created"] is True and fake.calls==[]

def execute(monkeypatch,fake,**kwargs):
    install(monkeypatch,fake); prepared=orch.prepare_publish_task(task(**kwargs)); return prepared,orch.execute_publish_task(prepared["task"]["id"],queue=PublishQueue())

def test_description_routes_to_instagram_caption(monkeypatch,isolated):
    fake=FakeTransport(); _,result=execute(monkeypatch,fake,description="caption text"); media=next(c for c in fake.calls if c[1].endswith("/media")); assert media[2]["params"]["caption"]=="caption text"; assert result["task"]["status"]=="published"

def test_title_is_caption_fallback(monkeypatch,isolated):
    fake=FakeTransport(); execute(monkeypatch,fake,description=""); media=next(c for c in fake.calls if c[1].endswith("/media")); assert media[2]["params"]["caption"]=="Title"

def test_execute_persists_provider_operation(monkeypatch,isolated):
    fake=FakeTransport(); _,result=execute(monkeypatch,fake); stored=result["task"]; assert stored["status"]=="published" and stored["platform_video_id"]=="media-1" and stored["provider_operation_id"]=="creation-1" and stored["provider_operation_status"]=="PUBLISHED"

def test_published_task_cannot_execute_twice(monkeypatch,isolated):
    fake=FakeTransport(); prepared,_=execute(monkeypatch,fake); count=len(fake.calls)
    with pytest.raises(Exception): orch.execute_publish_task(prepared["task"]["id"],queue=PublishQueue())
    assert len(fake.calls)==count

def test_atomic_claim_only_one_winner(monkeypatch,isolated):
    fake=FakeTransport(); install(monkeypatch,fake); prepared=orch.prepare_publish_task(task()); task_id=prepared["task"]["id"]; assert pm.claim_publish_task(task_id) is True; assert pm.claim_publish_task(task_id) is False; assert fake.calls==[]

def test_failure_after_container_preserves_operation(monkeypatch,isolated):
    fake=FakeTransport(fail_at=2); _,result=execute(monkeypatch,fake); stored=result["task"]; assert stored["status"]=="failed" and stored["provider_operation_id"]=="creation-1"

def test_retry_resumes_existing_operation(monkeypatch,isolated):
    fake=FakeTransport(fail_at=2); prepared,_=execute(monkeypatch,fake); fake.fail_at=None; fake.calls.clear(); fake.states=["FINISHED"]; result=orch.execute_publish_task(prepared["task"]["id"],queue=PublishQueue()); assert result["task"]["status"]=="published" and fake.calls[0][0]=="GET" and not any(c[1].endswith("/media") for c in fake.calls)

def test_resume_published_container_never_republishes(monkeypatch,isolated):
    fake=FakeTransport(states=["PUBLISHED"]); install(monkeypatch,fake); prepared=orch.prepare_publish_task(task())
    result=orch.execute_publish_task(prepared["task"]["id"],queue=PublishQueue())
    assert result["task"]["status"]=="failed"
    assert result["task"]["provider_operation_id"]=="creation-1"
    assert not any(c[1].endswith("/media_publish") for c in fake.calls)

def test_task_error_message_redacts_actual_token(monkeypatch,isolated):
    fake=FakeTransport(fail_at=1); _,result=execute(monkeypatch,fake); error=result["task"]["error_message"] or ""; assert TOKEN not in error and "Bearer" not in error and "Authorization" not in error

def test_test_database_is_not_production():
    assert os.environ.get("OS_TESTING")=="1"; assert str(pm.database_path()).lower()!=r"c:\users\l-r\desktop\remote-pay-guide-git\os\database\os.db"
