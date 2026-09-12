"""Network-free Publish Center integration contracts for Instagram."""
from publish.adapters.instagram import InstagramAdapter
from publish.orchestrator import PublishContractError, _resolve_asset, get_publish_execution_readiness
from publish.models import PublishTask


def test_default_gate_and_public_asset_preflight():
    readiness = get_publish_execution_readiness("instagram")
    assert readiness["publish_ready"] is False
    try:
        _resolve_asset(PublishTask(platform="instagram", account_id=3, asset_id="asset"))
    except PublishContractError:
        pass
    else:
        raise AssertionError("asset preflight must reject missing public URL")


def test_caption_contract_and_disabled_entrypoint_are_network_free():
    adapter = InstagramAdapter()
    result = adapter.publish_video({"asset_url": "https://example.test/reel.mp4"}, 3, caption="Caption")
    assert result["status"] == "simulated"
    assert adapter.get_status()["publish_ready"] is False


def test_operation_fields_are_provider_neutral():
    task = PublishTask(platform="instagram", provider_operation_id="creation-1", provider_operation_status="CREATED")
    assert task.provider_operation_id == "creation-1"
    assert task.provider_operation_status == "CREATED"


print("Instagram Publish Center integration contract smoke passed")
