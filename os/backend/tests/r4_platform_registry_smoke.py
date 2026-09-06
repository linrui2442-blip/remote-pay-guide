import importlib
import sys
import tempfile
from pathlib import Path

import data.platform_capabilities as platform_capabilities


with tempfile.TemporaryDirectory() as tmpdir:
    platform_capabilities.DB_PATH = Path(tmpdir) / "os.db"

    import publish.registry as registry

    expected = {"youtube", "tiktok", "instagram", "facebook"}
    registered = set(registry.list_registered_platforms())
    assert expected.issubset(registered), registered
    for platform in expected:
        adapter = registry.get_adapter(platform)
        assert adapter is not None
        assert adapter.get_status()["status"] == "ready"

    adapters_dir = Path(__file__).resolve().parents[1] / "publish" / "adapters"
    module_path = adapters_dir / "verifyfuture.py"
    module_name = "publish.adapters.verifyfuture"

    module_path.write_text(
        """
class VerifyFutureAdapter:
    platform_name = "verify-future"
    capabilities = {
        "analytics_supported": True,
        "oauth_required": True,
        "metric_types": ["views", "clicks"],
    }

    def __init__(self):
        self.status = "initialized"

    def initialize(self):
        self.status = "ready"
        return {"platform": self.platform_name, "status": self.status}

    def get_status(self):
        return {"platform": self.platform_name, "status": self.status}

    def publish_video(self, video_asset, account_id=None):
        return {"platform": self.platform_name, "status": "simulated"}
""".lstrip(),
        encoding="utf-8",
    )

    try:
        importlib.invalidate_caches()
        discovered = registry.discover_adapters()
        assert "verify-future" in discovered
        adapter = registry.get_adapter("verify-future")
        assert adapter is not None
        assert adapter.get_status()["status"] == "ready"

        capability = platform_capabilities.get_platform_capability("verify-future")
        assert capability["publish_supported"] is True
        assert capability["analytics_supported"] is True
        assert capability["oauth_required"] is True
        assert capability["metric_types"] == ["clicks", "views"]
    finally:
        module_path.unlink(missing_ok=True)
        sys.modules.pop(module_name, None)

print("platform registry smoke test passed")
