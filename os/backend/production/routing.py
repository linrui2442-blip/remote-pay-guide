"""Server-owned production provider routing for the G4 preparation phase."""
import os


PRODUCTION_ROUTER_VERSION = "g4-a-v1"
SUPPORTED_PROVIDERS = ("github", "ai_gateway")


def resolve_provider():
    configured = os.getenv("OS_PRODUCTION_PROVIDER")
    value = "github" if configured is None else configured.strip().lower()
    if value not in SUPPORTED_PROVIDERS:
        raise ValueError("unsupported OS_PRODUCTION_PROVIDER")
    return value


def resolve_route(plan_record):
    plan_id = plan_record.get("id")
    revision = plan_record.get("revision")
    configured = os.getenv("OS_PRODUCTION_PROVIDER")
    provider = resolve_provider()
    return {
        "router_version": PRODUCTION_ROUTER_VERSION,
        "selected_provider": provider,
        "selection_source": "server_default" if configured is None else "server_environment",
        "content_plan_id": plan_id,
        "content_plan_revision": revision,
        "reason_code": "DEFAULT_PROVIDER" if configured is None else "SERVER_PROVIDER_OVERRIDE",
    }


def validate_routing_evidence(evidence, *, plan_id, revision, provider=None):
    if not isinstance(evidence, dict):
        raise ValueError("production routing evidence is missing")
    allowed_keys = {"router_version", "selected_provider", "selection_source", "content_plan_id", "content_plan_revision", "reason_code"}
    if set(evidence) != allowed_keys:
        raise ValueError("production routing evidence contains unsupported fields")
    expected = {
        "router_version": PRODUCTION_ROUTER_VERSION,
        "content_plan_id": plan_id,
        "content_plan_revision": revision,
    }
    for key, value in expected.items():
        if evidence.get(key) != value:
            raise ValueError("production routing evidence is inconsistent")
    selected = evidence.get("selected_provider")
    if evidence.get("selection_source") not in {"server_default", "server_environment"}:
        raise ValueError("production routing source is inconsistent")
    expected_reason = "DEFAULT_PROVIDER" if evidence.get("selection_source") == "server_default" else "SERVER_PROVIDER_OVERRIDE"
    if evidence.get("reason_code") != expected_reason:
        raise ValueError("production routing reason is inconsistent")
    if selected not in SUPPORTED_PROVIDERS or (provider is not None and selected != provider):
        raise ValueError("production routing provider is inconsistent")
    return True
