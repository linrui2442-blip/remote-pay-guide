"""Network-free contract checks for the Instagram Reels adapter."""
from publish.adapters.instagram import InstagramAdapter


def test_adapter_is_registered_but_live_gate_remains_closed():
    status = InstagramAdapter().get_status()
    assert status["platform"] == "instagram"
    assert status["publish_ready"] is False
    assert status["execution_mode"] == "live_api"


def test_reels_requires_public_url():
    try:
        InstagramAdapter._video_url({"asset_url": "C:/private/video.mp4"})
    except ValueError as exc:
        assert "public http(s)" in str(exc)
    else:
        raise AssertionError("private path must not be accepted")
