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

The implemented policy and production layers are stage-aware:

```text
ContentPlan Policy Stage → Effective Authorization
→ G4-A prepare → server-owned Production Provider Route
→ ProductionTask → durable RuntimeJob claim
→ G4-B or G4-C provider execution → ProductionResult
→ G4-D asset quality → VideoAsset
→ G5 publishing → attribution → learning
```

G4-A is implemented and verified. G4-B, G4-C and G4-D remain incomplete.

G4 supports two production providers under one canonical lifecycle:
`github` and `ai_gateway`. Both pass through ContentPlan, G3 effective
authorization, server-owned routing, ProductionTask and RuntimeJob claim;
provider execution branches only after the RuntimeJob exists. There is no
parallel GitHub-specific or AI-specific orchestration lifecycle.

At the ContentPlan stage, `safety`, `novelty`, `duplicate_risk`, `account_health`, `platform_health`, `business` and generation assurance are required. `frequency`, `quality` and `cost` are `NOT_APPLICABLE` (not `PASS`) until their formal G5 or G4 gates exist.

The implemented safe path is:

```text
ContentPlan → Preview/Edit → Novelty → Human Approve
→ Human Create ProductionTask → Human Run → Human Publish
```

Manual and autonomous modes share ContentPlan, revision, novelty, policy,
approval/materialization, ProductionTask, execution readiness, scheduler and
runtime-claim primitives. Autonomous orchestration additionally requires a
fresh effective G3 authorization; generic manual lifecycle primitives do not
require autonomous authorization. No parallel `auto_*_v2` or direct-to-publish
lifecycle is canonical.

The G4-A runtime invariant is one ProductionTask to at most one canonical
RuntimeJob. The claim uses a SQLite durable transaction, idempotent
get-or-create behavior, ProductionTask state CAS and a partial unique
`task_id` index on clean history. Legacy duplicate rows are preserved and
claims fail closed rather than silently selecting a latest row.

G4-A owns authorization consumption, routing, materialization and RuntimeJob
claim. G4-B/C own provider execution and polling, G4-D owns the unified asset
quality gate, and G5 owns publishing policy and execution.

## Target policy decisions

`G3 Autonomous Policy Engine` is implemented and verified with persisted raw `AUTO` / `REVIEW` / `BLOCK` decisions, revision and policy-version binding, source fingerprints, history, concurrency/idempotency, evidence collection, human override, autonomy controls and effective authorization. At the ContentPlan stage, the legacy gate name `ai_confidence` means `generation assurance`, not model self-reported confidence or probability. Deferred gates are explicitly `NOT_APPLICABLE`: publishing frequency/cadence/rate/account controls belong to G5; production/provider cost policy and the asset quality gate belong to G4.

G3 is an authorization layer only. Raw or effective `AUTO` does not approve, materialize, run, render, create assets or publish. Automatic downstream consumption begins in G4/G5. `REVIEW` and `BLOCK` have no downstream execution until explicitly authorized.

## Canonical runtime components

- `os/backend`: API, lifecycle services, analytics/Data Center, production and publishing adapters.
- `os/frontend`: human-gated Intelligence → ContentPlan control surface.
- `os/database/os.db`: runtime state, never disposable test output.
- GitHub artifact → GitHub Pages → VideoAsset → official provider adapters: formal media/publishing path.

The deterministic ContentPlan provider is a development/fallback implementation behind the provider abstraction. A real OpenAI-compatible text provider and runtime provider selection are implemented, and the Sub2API + GPT-5.6 directed ContentPlan preview path has been verified through the canonical lifecycle. Human-directed and autonomous-compatible generation share this lifecycle; G3 policy-driven authorization and G4-A orchestration are implemented and verified, while provider execution, asset quality and publishing remain future G4-B/C/D and G5 work.

## Compatibility and legacy

Postiz paths, early `video-factory` scripts, old MVP dashboard/sync tooling, publish-existing-short workflows and snapshot → direct ProductionTask materialization are retained only for compatibility/history where needed. They are not the target autonomous runtime and must not be used by new frontend or autonomous scheduler code.

## Reading order

1. `docs/PROJECT_STATUS.md`
2. `docs/ARCHITECTURE.md`
3. Relevant subsystem document
4. Source code

Do not use dated reports or archive material to infer current requirements.
