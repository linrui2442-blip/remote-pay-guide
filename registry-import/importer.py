"""
Remote Pay Guide OS - Registry Import Execution Layer

Read-only importer.

Rules:
- dry-run by default
- never writes content-registry/registry.json
- never changes production or publish systems
"""

import json
from pathlib import Path

UNKNOWN = "UNKNOWN"


def load_json(path):
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_preview(tasks=None, artifacts=None, publishes=None):
    """Build preview data only. Does not persist registry changes."""
    return {
        "mode": "dry_run",
        "registry_write": False,
        "sources": {
            "tasks": str(tasks or "UNKNOWN"),
            "artifacts": str(artifacts or "UNKNOWN"),
            "publish_state": str(publishes or "UNKNOWN")
        },
        "items": []
    }


if __name__ == "__main__":
    print(json.dumps(build_preview(), indent=2))
