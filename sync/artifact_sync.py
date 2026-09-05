"""
Read-only artifact metadata synchronizer.

Phase 5:
- Reads existing artifact metadata only.
- Produces artifact reports.
- Does not modify registry or production files.
"""

import json
from pathlib import Path
from typing import Any


def build_artifact_report(metadata: dict[str, Any], artifact_id: str = "UNKNOWN") -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "content_id": metadata.get("content_id", "UNKNOWN"),
        "status": metadata.get("status", "UNKNOWN"),
        "output": metadata.get("output", "UNKNOWN"),
        "sync_mode": "read_only",
    }


def read_metadata(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    print(json.dumps({"report": "artifact report", "sync_mode": "read_only"}, indent=2))
