# Canonical Architecture

This document defines the canonical runtime and target architecture. The target product is an **Autonomous Content Growth OS**. Human-gated execution is a safety, validation, fallback, review and override mode, not the final production operating model.

## Truth hierarchy

Source code is authoritative for actual behavior. `docs/PROJECT_STATUS.md` is authoritative for current state. This document is authoritative for intended canonical and target architecture. Supporting and historical documents cannot override those sources.

## Runtime boundary

```text
Source code → Git repository
Runtime state → os/database/os.db
```

The production database is preserved separately and is never a test database.

## One canonical lifecycle

```text
Data ingestion → Data Center → Intelligence / AI Brain → ContentPlan
→ Novelty / Safety / Quality / Business Policy → AUTO / REVIEW / BLOCK
```

The implemented safe path is:

```text
ContentPlan → Preview/Edit → Novelty → Human Approve
→ Human Create ProductionTask → Human Run → Human Publish
```

Manual and autonomous modes share one lifecycle. The difference is who initiates actions: a human in Manual Mode, or a policy/orchestrator in Autonomous Mode. Future orchestration must call existing ContentPlan, revision guard, novelty, approval, materialization, ProductionTask, readiness, VideoAsset, PublishTask, recovery, idempotency and concurrency services. No parallel `auto_*_v2` or direct-to-publish lifecycle is canonical.

## Target policy decisions

`AUTO` proceeds only when novelty, AI confidence, quality, duplicate risk, account/platform health, frequency, performance, business, cost and safety constraints pass. `REVIEW` enters a human queue for low confidence, borderline novelty, unusual strategy/CTA, account warnings or policy uncertainty. `BLOCK` stops for duplicates, invalid assets, broken lifecycle, unsafe accounts/content, missing credentials, rate risk or inconsistent state. This is target architecture, not an implementation claim.

For `AUTO`, the canonical continuation is approve → materialize → run → render → asset quality gate → schedule → publish → attribution → learning. `REVIEW` and `BLOCK` have no downstream execution until explicitly authorized.

## Canonical runtime components

- `os/backend`: API, lifecycle services, analytics/Data Center, production and publishing adapters.
- `os/frontend`: human-gated Intelligence → ContentPlan control surface.
- `os/database/os.db`: runtime state, never disposable test output.
- GitHub artifact → GitHub Pages → VideoAsset → official provider adapters: formal media/publishing path.

The deterministic ContentPlan provider is a development/fallback implementation behind the provider abstraction. A real OpenAI-compatible text provider and runtime provider selection are implemented, and the Sub2API + GPT-5.6 directed ContentPlan preview path has been verified through the canonical lifecycle. Human-directed and autonomous-compatible generation share this lifecycle; policy-driven AUTO/REVIEW/BLOCK orchestration remains future G3 work.

## Compatibility and legacy

Postiz paths, early `video-factory` scripts, old MVP dashboard/sync tooling, publish-existing-short workflows and snapshot → direct ProductionTask materialization are retained only for compatibility/history where needed. They are not the target autonomous runtime and must not be used by new frontend or autonomous scheduler code.

## Reading order

1. `docs/PROJECT_STATUS.md`
2. `docs/ARCHITECTURE.md`
3. Relevant subsystem document
4. Source code

Do not use dated reports or archive material to infer current requirements.
