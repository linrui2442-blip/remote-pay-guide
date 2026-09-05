"""
Read-only publish state synchronizer.

Phase 5:
- Reads existing publish-state data only.
- Produces publish reports.
- Does not call Postiz API.
- Does not update registry.
"""

import json
from pathlib import Path
from typing import Any


def build_publish_report(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "content_id": state.get("content_id", "UNKNOWN"),
        "postiz_id": state.get("postiz_id", "UNKNOWN"),
        "platforms": state.get("platforms", {}),
        "published_url": state.get("published_url", {}),
        "publish_status": state.get("status", "UNKNOWN"),
        "sync_mode": "read_only",
    }


def read_publish_state(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    print(json.dumps({"report": "publish report", "sync_mode": "read_only"}, indent=2))
