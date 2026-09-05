"""
Read-only analytics data validator.

Phase 5:
- Validates analytics payload format only.
- Does not connect to GA4 API.
- Does not write metrics back.
"""

from typing import Any

REQUIRED_FIELDS = [
    "content_id",
    "platform",
    "views",
    "clicks",
    "conversion",
]


def validate_metric(payload: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    return {
        "valid": len(missing) == 0,
        "missing_fields": missing,
        "sync_mode": "read_only",
    }


if __name__ == "__main__":
    print({"validator": "analytics", "sync_mode": "read_only"})
