"""Canonical G4-A authorized preparation boundary.

This module deliberately stops after ContentPlan materialization. It never
creates runtime jobs, dispatches providers, creates results/assets, or
publishes anything.
"""
from intelligence import autonomy
from intelligence.content_brain import get_plan
from intelligence.content_plan_service import approve_plan, materialize_plan
from production.routing import resolve_route
from production.tasks.manager import get_task_by_idempotency_key
from production.tasks.execution import get_execution_readiness
from production.tasks.scheduler import claim_runtime_job
from intelligence.content_plan_service import _validate_materialized_task


def _authorization_or_fail(plan_id, plan):
    authorization = autonomy.get_effective_authorization(plan_id)
    if authorization.get("policy_version") != "g3-v2":
        raise ValueError("current g3-v2 authorization required")
    if authorization.get("current_revision") != plan.get("revision"):
        raise ValueError("stale authorization revision")
    if plan.get("status") == "superseded":
        raise ValueError("superseded content plan cannot be prepared")
    if not authorization.get("autonomous_continuation_allowed"):
        raise ValueError("effective autonomous authorization is not allowed")
    return authorization


def prepare_authorized_production(plan_id):
    plan = get_plan(plan_id)
    if not plan:
        raise KeyError("plan not found")

    # Route preflight is intentionally before approval and materialization.
    route = resolve_route(plan)
    authorization = _authorization_or_fail(plan_id, plan)

    authorized_revision = authorization["current_revision"]
    if plan.get("status") == "preview":
        try:
            approve_plan(plan_id, expected_revision=authorized_revision)
        except ValueError:
            latest = get_plan(plan_id)
            if not latest or latest.get("revision") != plan.get("revision") or latest.get("status") not in {"approved", "materialized"}:
                raise
    # Authorization is a lease-like decision, not a one-time observation.
    # Recheck immediately before the first durable ProductionTask insert.
    latest_before_materialize = get_plan(plan_id)
    authorization = _authorization_or_fail(plan_id, latest_before_materialize)
    if authorization.get("current_revision") != authorized_revision:
        raise ValueError("authorization revision changed during preparation")
    task = materialize_plan(plan_id, _route=route)
    latest = get_plan(plan_id)
    persisted_route = (task.parameters or {}).get("production_routing")
    returned_route = persisted_route or {
        "routing_evidence_status": "legacy_existing",
        "selected_provider": task.provider,
        "content_plan_id": plan_id,
        "content_plan_revision": latest.get("revision"),
    }
    return {
        "authorization": authorization,
        "routing": returned_route,
        "content_plan": latest,
        "production_task": task,
        "execution": "not_started",
    }


def claim_authorized_production_execution(plan_id):
    """Fresh-auth, durable handoff to exactly one RuntimeJob; never runs a provider."""
    plan = get_plan(plan_id)
    if not plan:
        raise KeyError("plan not found")
    if plan.get("status") != "materialized":
        raise ValueError("production plan must be materialized before execution claim")
    revision = plan.get("revision")
    key = f"content-plan:{plan_id}:revision:{revision}"
    task = get_task_by_idempotency_key(key)
    if not task:
        raise ValueError("canonical ProductionTask is missing")
    if not task.parameters.get("production_routing"):
        raise ValueError("legacy task requires review before autonomous execution")
    _validate_materialized_task(task, plan_id, revision, key)
    auth = _authorization_or_fail(plan_id, plan)
    job = claim_runtime_job(task)
    return {
        "content_plan": get_plan(plan_id),
        "authorization": auth,
        "production_task": task,
        "runtime_job": job,
        "provider": task.provider,
        "claim_status": "claimed",
        "execution_readiness": get_execution_readiness(task),
    }
