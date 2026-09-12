"""Network-free three-layer Instagram operational readiness contract."""

import json
from datetime import datetime, timedelta, timezone

from publish.adapters import instagram as instagram_module
from publish.adapters.instagram import InstagramAdapter
from publish.registry import discover_adapters
from publish.manager import get_publish_tasks


def _metadata(monkeypatch, *, account=True, binding=True, token=True, scopes=None, expires_at=None):
    monkeypatch.setattr(instagram_module, "get_account", lambda _: {"id": 3, "platform": "instagram"} if account else None)
    monkeypatch.setattr(instagram_module, "get_binding", lambda _: {"platform": "instagram", "instagram_user_id": "ig-3", "page_id": "page-2"} if binding else None)
    if token:
        token_row = {"provider": "instagram", "access_token": "opaque", "scopes": scopes or list(instagram_module.INSTAGRAM_PUBLISH_SCOPES), "expires_at": expires_at}
    else:
        token_row = None
    monkeypatch.setattr(instagram_module, "get_token", lambda _: token_row)


def test_implementation_exists_and_default_gate_is_closed(monkeypatch):
    monkeypatch.delenv("META_INSTAGRAM_LIVE_PUBLISH_ENABLED", raising=False)
    adapter = InstagramAdapter()
    status = adapter.get_status()
    assert status["implementation_ready"] is True
    assert status["configuration_ready"] is False
    assert status["publish_ready"] is False
    assert status["execution_mode"] == "simulated"


def test_complete_local_metadata_plus_explicit_gate(monkeypatch):
    _metadata(monkeypatch)
    monkeypatch.setenv("META_INSTAGRAM_LIVE_PUBLISH_ENABLED", "true")
    adapter = InstagramAdapter()
    status = adapter.get_status()
    account = adapter.get_account_readiness(3)
    assert status["configuration_ready"] is True
    assert account["ready"] is True


def test_explicit_gate_disable_and_missing_binding_or_token(monkeypatch):
    monkeypatch.setenv("META_INSTAGRAM_LIVE_PUBLISH_ENABLED", "false")
    _metadata(monkeypatch, binding=False)
    assert InstagramAdapter().get_account_readiness(3)["ready"] is False
    _metadata(monkeypatch, token=False)
    assert InstagramAdapter().get_account_readiness(3)["ready"] is False


def test_missing_scopes_and_expired_token_fail_closed(monkeypatch):
    _metadata(monkeypatch, scopes=["instagram_basic"])
    assert InstagramAdapter().get_account_readiness(3)["ready"] is False
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    _metadata(monkeypatch, expires_at=expired)
    assert InstagramAdapter().get_account_readiness(3)["ready"] is False


def test_readiness_is_side_effect_free_and_does_not_call_graph(monkeypatch):
    calls = []
    class Transport:
        def __getattr__(self, name):
            return lambda *args, **kwargs: calls.append((name, args, kwargs))
    _metadata(monkeypatch)
    adapter = InstagramAdapter(transport=Transport())
    adapter.get_status()
    adapter.get_account_readiness(3)
    assert calls == []


def test_readiness_does_not_create_publish_tasks(monkeypatch):
    _metadata(monkeypatch)
    before = len(get_publish_tasks())
    adapter = InstagramAdapter()
    adapter.get_status()
    adapter.get_account_readiness(3)
    assert len(get_publish_tasks()) == before


def test_gate_is_not_a_credential_store(monkeypatch):
    monkeypatch.setenv("META_INSTAGRAM_LIVE_PUBLISH_ENABLED", "1")
    config = instagram_module.meta_runtime_config()
    assert config["instagram_live_publish_enabled"] is True
    assert "access_token" not in json.dumps(config)
    assert "client_secret" not in json.dumps(config)


def test_registry_auto_discovery_keeps_production_default_closed(monkeypatch):
    monkeypatch.delenv("META_INSTAGRAM_LIVE_PUBLISH_ENABLED", raising=False)
    discover_adapters()
    adapter = InstagramAdapter()
    assert adapter.get_status()["publish_ready"] is False
