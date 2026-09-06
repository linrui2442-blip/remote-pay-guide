import importlib
import inspect
import pkgutil

import publish.adapters as adapters_package
from data.platform_capabilities import (
    get_platform_capability,
    register_platform_capability,
)


platform_registry = {}


def _normalize_platform(platform):
    if not isinstance(platform, str):
        return None
    normalized = platform.strip().lower()
    return normalized or None


def register_adapter(platform, adapter, *, initialize=True, replace=False):
    """Register a publish adapter without changing Publish Center core code."""
    normalized = _normalize_platform(platform)
    if not normalized:
        raise ValueError("platform is required")
    if adapter is None:
        raise ValueError("adapter is required")

    if normalized in platform_registry and not replace:
        return platform_registry[normalized]

    if initialize and hasattr(adapter, "initialize"):
        adapter.initialize()

    platform_registry[normalized] = adapter

    # Keep the Data Center aware of newly discovered publish platforms while
    # preserving any capability metadata that has already been configured.
    if get_platform_capability(normalized) is None:
        register_platform_capability(
            normalized,
            publish_supported=True,
            analytics_supported=False,
            oauth_required=False,
            metric_types=[],
        )

    return adapter


def _adapter_class_from_module(module):
    candidates = []
    for _, candidate in inspect.getmembers(module, inspect.isclass):
        if candidate.__module__ != module.__name__:
            continue
        if candidate.__name__.endswith("Adapter"):
            candidates.append(candidate)

    if len(candidates) == 1:
        return candidates[0]
    return None


def discover_adapters():
    """Auto-discover one *Adapter class per module under publish.adapters.

    Helper/API modules that do not define an Adapter class are ignored. A new
    platform can therefore be added as a new adapter module without editing
    this registry.
    """
    discovered = []
    for module_info in pkgutil.iter_modules(adapters_package.__path__):
        module_name = module_info.name
        if module_name.startswith("_"):
            continue

        module = importlib.import_module(f"{adapters_package.__name__}.{module_name}")
        adapter_class = _adapter_class_from_module(module)
        if adapter_class is None:
            continue

        adapter = adapter_class()
        register_adapter(module_name, adapter)
        discovered.append(module_name)

    return sorted(discovered)


def get_adapter(platform):
    normalized = _normalize_platform(platform)
    if not normalized:
        return None
    return platform_registry.get(normalized)


def list_registered_platforms():
    return sorted(platform_registry)


def get_registry_status():
    result = []
    for platform in list_registered_platforms():
        adapter = platform_registry[platform]
        status = adapter.get_status() if hasattr(adapter, "get_status") else None
        result.append(
            {
                "platform": platform,
                "adapter": adapter.__class__.__name__,
                "status": status,
            }
        )
    return result


# Preserve the existing import-time registry behavior while removing the
# hard-coded list of platforms.
discover_adapters()
