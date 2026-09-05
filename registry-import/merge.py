#!/usr/bin/env python3
"""Controlled Registry Merge - dry run only.

This script compares registry-import/preview.json with
content-registry/registry.json and generates proposed changes.
It never writes registry.json.
"""

import json
from pathlib import Path

DRY_RUN = True
REGISTRY_WRITE = False

BASE = Path(__file__).resolve().parent.parent
PREVIEW = BASE / "registry-import" / "preview.json"
REGISTRY = BASE / "content-registry" / "registry.json"
OUTPUT = BASE / "registry-import" / "proposed_changes.json"
REPORT = BASE / "registry-import" / "merge_report.json"


def load_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def compare(old, new, content_id, changes, skipped, unknown):
    keys = set(old.keys()) | set(new.keys())
    for key in keys:
        old_value = old.get(key, "UNKNOWN")
        new_value = new.get(key, "UNKNOWN")

        if new_value == "UNKNOWN":
            unknown.append({"content_id": content_id, "field": key})
            continue

        if old_value == new_value:
            skipped.append({"content_id": content_id, "field": key})
            continue

        if old_value == "UNKNOWN":
            changes.append({
                "content_id": content_id,
                "field": key,
                "old_value": old_value,
                "new_value": new_value,
                "change_type": "UNKNOWN_REPLACED"
            })
        else:
            skipped.append({"content_id": content_id, "field": key, "reason": "existing_value_preserved"})


def main():
    preview = load_json(PREVIEW)
    registry = load_json(REGISTRY)

    changes = []
    skipped = []
    unknown = []

    preview_items = preview.get("items", []) if isinstance(preview, dict) else []
    registry_items = {x.get("content_id"): x for x in registry.get("contents", [])} if isinstance(registry, dict) else {}

    for item in preview_items:
        cid = item.get("content_id", "UNKNOWN")
        compare(registry_items.get(cid, {}), item, cid, changes, skipped, unknown)

    OUTPUT.write_text(json.dumps({"dry_run": DRY_RUN, "registry_write": REGISTRY_WRITE, "changes": changes}, indent=2), encoding="utf-8")
    REPORT.write_text(json.dumps({
        "changed_fields": len(changes),
        "skipped_fields": len(skipped),
        "unknown_fields": len(unknown)
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
