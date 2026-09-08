"""Provider-neutral conversion adapter boundary.

Official provider integrations register here when their verified callback/API
contract is available. No provider is assumed or fabricated by this module.
"""
from typing import Any


class ConversionAttributionAdapter:
    provider_name = ""

    def verify_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def normalize_conversion(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def external_event_id(self, payload: dict[str, Any]) -> str | None:
        return payload.get("external_conversion_id")

    def resolve_attribution(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload


_ADAPTERS: dict[str, ConversionAttributionAdapter] = {}


def register_conversion_adapter(adapter: ConversionAttributionAdapter):
    name = str(adapter.provider_name or "").strip().lower()
    if not name:
        raise ValueError("conversion adapter provider_name is required")
    _ADAPTERS[name] = adapter
    return adapter


def get_conversion_adapter(provider: str):
    return _ADAPTERS.get(str(provider or "").strip().lower())


def list_conversion_adapters():
    return sorted(_ADAPTERS)
