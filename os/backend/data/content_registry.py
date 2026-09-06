import json
from pathlib import Path


REGISTRY_PATH = Path("content-registry/registry.json")


def _load_registry():
    if not REGISTRY_PATH.exists():
        return []

    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("assets"), list):
        return [item for item in raw["assets"] if isinstance(item, dict)]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def get_contents():
    """Read the existing Content Registry without mutating legacy state."""
    return _load_registry()


def get_content(content_id):
    if not content_id:
        return None
    return next(
        (item for item in _load_registry() if item.get("content_id") == content_id),
        None,
    )
