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

G4-A and G4-B are implemented and verified, including the G4-B real live
GitHub render/artifact/Pages promotion proof. G4-C owns AI provider execution/
polling and is offline-certified, with real provider proof pending configuration.
G4-D is offline-certified and remains the sole new autonomous owner of the
unified asset quality gate and promotion into VideoAsset. Its real read-only
media proof is non-blocking pending after two fail-safe media-read failures;
neither G4-C nor G4-D is CLOSED. No further automatic live retry is permitted.

G6 uses `intelligence.learning.run_feedback_cycle()` to read persisted Data
Center evidence for a mature account/platform window. It extends the existing
FeedbackSnapshot with a generation claim and plan link, not a second lifecycle.
Fingerprinting includes cohort/window/metric/funnel evidence. Only the claim
winner invokes the existing provider abstraction. Interrupted generation is
REVIEW; a persisted linked plan can resume local policy evaluation without
calling the provider again. The endpoint is a preview plus PolicyDecision,
never approval, production or publishing. Analytics refresh remains in existing
integrations and is not implicitly invoked by the cycle. Observational strategy
language must not assert causal effects from cohort outcomes.

G7 operational health is a read-only projection of canonical tables, not a
second queue or scheduler. Stale entities are review items identified by their
existing IDs. Local reconciliation delegates to existing publish/feedback
methods; production/provider recovery still requires the original verified
evidence and authorization boundary. It never retries an ambiguous POST.
Missing tables/configuration/readiness are reported rather than treated as
healthy. See README for isolated startup, backup/restore and incident procedures.

G4-B consumes an existing claimed RuntimeJob. Durable execution and promotion
claims precede external POSTs; asynchronous polling, deterministic artifact
discovery, crash/recovery/concurrency protection and terminal result replay
prevent duplicate dispatch. Its verified Pages promotion stops at
ProductionResult, without creating VideoAsset or PublishTask.

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

G4-D uses `assets.quality.evaluate_production_result_asset(result_id)` for both
providers. `asset_quality_checks` persists `g4d-v1` decisions and immutable
source fingerprints. Clean histories have partial unique indexes on the
result identity in quality checks and VideoAssets; duplicate legacy history is
preserved and rejected. Technical PASS, deterministic `asset-result-{id}`
creation and ProductionResult asset binding finalize atomically. The completed
result's remote correlation/output and historical deferral marker stay intact.
REVIEW may retry the same check; BLOCK and PASS are terminal for that source
and policy. There is no parallel provider-specific asset lifecycle.

`assets.remote_media` is a separate read-only security boundary, not the legacy
publish resolver. It validates HTTPS/443, credentials, hosts and all resolved
addresses at every redirect, pins the TLS connection to a validated IP while
verifying the original hostname, disables automatic redirects/decompression,
limits downloads to 32 KiB–500 MiB, and cleans external temporary files.
ffprobe runs without a shell, with protocol/format restrictions and a timeout.
Technical v1 requires a video stream, finite 3–180 second duration, at least
360×640 dimensions and a 0.50–0.65 aspect ratio. Audio presence is recorded but
optional. Unavailable inspection returns REVIEW, never fabricated PASS.

Quality evidence contains bounded technical fields and URL fingerprints, not
signed URL queries or secret headers. The canonical asset retains the source
URL, not its temporary inspection path. G4-D never queues or publishes; G5
remains the publishing owner. ContentPlan-stage quality remains deferred to
this later asset stage; technical certification is not semantic moderation.

## Target policy decisions

`G3 Autonomous Policy Engine` is implemented and verified with persisted raw `AUTO` / `REVIEW` / `BLOCK` decisions, revision and policy-version binding, source fingerprints, history, concurrency/idempotency, evidence collection, human override, autonomy controls and effective authorization. At the ContentPlan stage, the legacy gate name `ai_confidence` means `generation assurance`, not model self-reported confidence or probability. Deferred gates are explicitly `NOT_APPLICABLE`: publishing frequency/cadence/rate/account controls belong to G5; production/provider cost policy and the asset quality gate belong to G4.

G3 is an authorization layer only. Raw or effective `AUTO` does not approve, materialize, run, render, create assets or publish. Automatic downstream consumption begins in G4/G5. `REVIEW` and `BLOCK` have no downstream execution until explicitly authorized.

## Canonical runtime components

- `os/backend`: API, lifecycle services, analytics/Data Center, production and publishing adapters.
- `os/frontend`: human-gated Intelligence → ContentPlan control surface.
- `os/database/os.db`: runtime state, never disposable test output.
- GitHub artifact → GitHub Pages → VideoAsset → official provider adapters: formal media/publishing path.

The deterministic ContentPlan provider is a development/fallback implementation behind the provider abstraction. A real OpenAI-compatible text provider and runtime provider selection are implemented, and the Sub2API + GPT-5.6 directed ContentPlan preview path has been verified through the canonical lifecycle. Human-directed and autonomous-compatible generation share this lifecycle; G3 policy-driven authorization, G4-A orchestration and G4-B GitHub execution are verified. G4-C execution and G4-D asset quality are offline-certified but still await their respective live proofs. G5 publishing is offline-certified, not live-closed.

## G5 publishing stage

G5 reuses `PublishTask`, Publish Center, registry, worker, scheduler, Accounts /
OAuth and the official YouTube, Instagram and Facebook adapters. No V2 queue,
alternative asset type or parallel publishing domain is introduced. TikTok is
not a v1 launch requirement; Postiz is not a canonical dependency.

`publish.policy.prepare_autonomous_publish_task` evaluates `g5-v1` and only
AUTO materializes a task. Policy evidence and a frozen payload/source
fingerprint live on that task. Required signals include G4-D PASS and exact
asset binding, account/platform/scopes/expiry readiness, the shared autonomy
controls, duplicate history, schedule and cadence. Unknown signals are REVIEW;
hard failures are BLOCK. The deterministic cadence is one-hour minimum and
three-per-UTC-day maximum per platform/account, counting reservations and
ambiguous execution conservatively. Future schedules require reevaluation;
the existing scheduler queues due pending tasks only.

Existing orchestrator/worker entrypoints recognize autonomous tasks and route
them through `publish.execution.execute_autonomous_publish_task`. Manual
legacy tasks retain their existing contract. Clean histories receive active
identity uniqueness plus a cross-status autonomous identity index. Legacy
duplicates are never deleted or silently selected. An immutable owner claim,
`publish_write_intents` (unique task/stage) and `publish_operation_events`
provide execution evidence, not new lifecycle entities.

Each provider write is preceded by a committed intent and a fresh policy /
control check. SQLite transactions end before network calls. YouTube reuses
its resumable upload transport and the shared secure G4-D downloader; its
session identity is persisted as a hash rather than a bearer URL. Instagram
retains container then media identity; Facebook retains start/upload/publish
state. Autonomous HTTP redirects are disabled and upload destinations are
restricted to the provider's expected HTTPS hosts. Provider errors are reduced
to safe reason codes; successful completion emits the existing OS event.

`reconcile_autonomous_publish_task` never resumes a write. A fresh owner is
left alone; after interruption, durable successful media evidence can finish
the local task and event atomically. Missing/ambiguous response evidence stays
REVIEW. Neither unknown outcomes nor expired claims authorize a second upload.
Terminal replay has zero provider writes. This deliberately does not assert
remote exactly-once semantics; YouTube may retry resumable chunks within the
same session under its existing protocol.

Offline tests use external TEMP databases, socket tripwires and fake provider
transports. G4-D live media proof and separate G5 platform live proofs are still
authorization gates; offline certification does not close those milestones.

## Compatibility and legacy

Postiz paths, early `video-factory` scripts, old MVP dashboard/sync tooling, publish-existing-short workflows and snapshot → direct ProductionTask materialization are retained only for compatibility/history where needed. They are not the target autonomous runtime and must not be used by new frontend or autonomous scheduler code.

## Reading order

1. `docs/PROJECT_STATUS.md`
2. `docs/ARCHITECTURE.md`
3. Relevant subsystem document
4. Source code

Do not use dated reports or archive material to infer current requirements.
