# Canonical Project Status

This document is the single source of truth for the current Remote Pay Guide OS implementation state. If another document conflicts with this file on current completion, runtime readiness, blockers, or priorities, this file wins. Historical material is non-canonical.

## Product definition

Remote Pay Guide OS is an **AUTONOMOUS CONTENT GROWTH OS**. Its target loop is real platform, website, referral and conversion data → Data Center → Intelligence / real AI → ContentPlan → policy decision → production → quality gate → publishing → attribution → feedback learning.

The current human-gated path is **SAFE / MANUAL MODE**:

```text
Intelligence → ContentPlan → Preview/Edit → Novelty → Human Approve
→ Human Create ProductionTask → Human Run → Human Publish
```

This mode is a development, validation, fallback, review, recovery and override safety layer. Human approval is not the final autonomous product target.

## Current main

```text
Current canonical branch: main
P3=CLOSED
```

## Completed or substantially implemented

Accounts and OAuth foundations; YouTube runtime; analytics and historical/backfill foundations; Data Center; ProductionTask lifecycle; GitHub production/render and artifact handling; VideoAsset; publish infrastructure; recovery, idempotency and concurrency guards; Intelligence snapshots; ContentPlan persistence and revision lifecycle; canonical novelty PASS/WARN/BLOCK; human approval; materialization; and the frontend human-gated ContentPlan flow.

G2 real AI content brain is closed: the OpenAI-compatible TextProvider, runtime provider selection, Sub2API with GPT-5.6, directed human constraints, strict JSON parsing, generated and final safety floors, locked fields, trusted production specification, and preview persistence were verified through the canonical route using an isolated database.

These labels describe implementation and verified contracts where applicable; code presence is not automatically a real external-runtime guarantee.

### Completed milestone — Autonomous Policy Engine

`G3_AUTONOMOUS_POLICY_ENGINE=CLOSED`.

The policy engine persists revision-bound, policy-version-bound raw `PolicyDecision` rows with source fingerprints, immutable history, concurrency/idempotency protection and `AUTO` / `REVIEW` / `BLOCK` outcomes. It combines canonical safety and novelty evidence, duplicate risk derived from novelty, account/platform health, business evidence, generation assurance, human override and clear audit, strict request contracts, autonomy enablement, kill switch, review queue and effective authorization.

`POLICY_VERSION=g3-v2`
`POLICY_STAGE=content_plan`

For the ContentPlan stage, required gates are `safety`, `novelty`, `duplicate_risk`, `account_health`, `platform_health`, `business` and `ai_confidence` (whose canonical meaning is generation assurance, not model probability). `frequency`, `quality` and `cost` are explicitly `NOT_APPLICABLE`, not fake `PASS`: they are deferred respectively to G5 publishing policy, the G4-D asset quality gate and G4 production/provider cost policy.

G3 produces authorization only. Even when raw `AUTO` and effective continuation are allowed, G3 does not approve, materialize, create or run a ProductionTask, render, create a VideoAsset or PublishTask, or publish. Those downstream consumers begin in G4/G5.

## Current breakpoints

### Completed milestone — GA4 attribution runtime

`G1_D10_REAL_GA4_RUNTIME=CLOSED`.
`D10_GA4_STATUS=CLOSED`.
`GA4_ATTRIBUTION_LIVE_E2E=PASS`.

Standard Reporting proved `content_id=short12`, `src=yt_short12`, and `binance_referral_click=1`, followed by canonical `ga4.sync`, real Data API ingestion into an isolated database, Data Center visibility, Intelligence feedback analysis, and idempotent replay. Binance registration, deposit, trading and revenue conversion remain deferred.

### Completed milestone — real AI content brain

`G2_REAL_AI_CONTENT_BRAIN=CLOSED`.

`REAL_AI_CONTENTPLAN_LIVE_E2E=PASS`. The deterministic provider remains a development/fallback implementation; the real text-AI provider and canonical directed ContentPlan preview path are verified.

### Completed milestone — G4-A Unified Production Orchestration

`G4A_UNIFIED_PRODUCTION_ORCHESTRATION=CLOSED`.
`G4_STATUS=IN_PROGRESS`.

G4-A consumes current `g3-v2` effective authorization: the plan revision
must match, effective policy must be `AUTO`, autonomy must be enabled and the
kill switch must be off. Provider routing is server-owned (`g4-a-v1`) and
supports `github` and `ai_gateway`; client or model output cannot select an
endpoint or credential. One current ContentPlan revision materializes exactly
one canonical ProductionTask with idempotency key
`content-plan:{plan_id}:revision:{revision}`. The execution claim performs a
fresh authorization recheck and durably claims exactly one RuntimeJob using a
SQLite transaction, database-level duplicate protection and fail-closed
handling for legacy duplicate history.

G4-A stops before provider execution, GitHub workflow dispatch, AI Gateway
HTTP, ProductionResult, VideoAsset, PublishTask and publishing. Manual mode
remains supported and shares the canonical lifecycle primitives. G4-B must
consume an existing claimed GitHub RuntimeJob rather than re-route,
re-materialize, schedule a second task or create a second RuntimeJob. G4-C
will reuse the same ContentPlan, routing, ProductionTask and RuntimeJob
foundation for real AI production; G4-D remains the unified asset quality
gate.

### Completed milestone — G4-B GitHub Production Line

`G4B_GITHUB_PRODUCTION_LINE=CLOSED`
`G4C_REAL_AI_PRODUCTION_LINE=IN_PROGRESS`
`G4C_OFFLINE_CERTIFIED=PASS`
`G4C_REAL_LIVE_E2E=PENDING_CONFIGURATION`
`G4D_UNIFIED_ASSET_QUALITY_GATE=IN_PROGRESS`
`G4D_OFFLINE_CERTIFIED=PASS`
`G4D_REAL_LIVE_E2E=LIVE_BLOCKED_BY_UNRESOLVED_MEDIA_READ`
`G4D_STATUS=NON_BLOCKING_LIVE_PENDING`

G4-B consumes the existing claimed RuntimeJob, persists durable GitHub
execution intent before dispatch, and provides at-most-once render dispatch,
async polling and deterministic artifact discovery. A durable promotion claim
precedes its POST, protecting at-most-once promotion against concurrent callers
and crash/recovery replay. ProductionResult terminal replay is idempotent.
The real live E2E passed: render run `36663762855`, artifact `11075661148`
(`remote-pay-guide-g4b-live-invoice-currency`), and promotion run `36664084889`
all succeeded. GitHub Pages serves `media/g4b-live-invoice-currency.mp4`
(11,786,732 bytes). This proof created no VideoAsset or PublishTask.
G4-C owns AI execution/polling; G4-D remains responsible for unified asset
quality and VideoAsset creation. G4-C is not yet closed.

### Offline-certified milestone — G4-D Unified Asset Quality Gate

The provider-neutral `g4d-v1` gate consumes completed, linked, deferred
ProductionResults from GitHub or AI. It records one durable quality check per
result and creates a deterministic VideoAsset only on technical `PASS`, with
asset creation and result binding in one transaction. `REVIEW` is retryable;
`BLOCK` and `PASS` replay without repeating inspection. Source drift and legacy
duplicate quality/asset history fail closed without deleting history.

The read-only downloader enforces HTTPS/443, public DNS/IP validation on every
redirect, DNS-pinned TLS connections, size limits and external TEMP cleanup.
The ffprobe gate checks video structure, duration (3–180 seconds), minimum
360×640 dimensions and portrait aspect (0.50–0.65). Missing ffprobe or temporary
fetch/DNS failures require review. Audio presence is evidence, not mandatory.
This is technical validation, not perceptual quality, copyright or semantic
moderation. Signed URL queries are not copied into quality evidence.

Both providers, failure/review matrices, atomic rollback, 20 rounds of four
concurrent callers, and legacy compatibility were verified offline. G4-C still
stops before asset creation; deferred results cannot use legacy binding as a
shortcut. G4-D creates no PublishTask. Neither G4-C nor G4-D is CLOSED.
Two authorized read-only G4-D proofs failed safely with REMOTE_FETCH_UNAVAILABLE;
the second received HTTP 200 but did not verify the full body. No deterministic
downloader defect is established. Do not automatically retry or weaken SSRF/TLS.
G4-C configuration and G4-D live verification are non-blocking pending gates.
Production DB remains unchanged.

### Offline-certified milestone — G5 Autonomous Publishing

`G5_OFFLINE_CERTIFIED=PASS`
`G5_STATUS=OFFLINE_CERTIFIED_PUSHED_AWAITING_AUTHORIZED_LIVE_PROOFS`
`G5_REAL_PLATFORM_PUBLISH_PROOF=NOT_RUN`

`publish.policy.prepare_autonomous_publish_task()` applies server-owned
`g5-v1` policy to the existing VideoAsset/PublishTask lifecycle. Only AUTO can
create an autonomous task. It requires current G4-D PASS/binding, a ready
account and official adapter, valid scoped non-expired credentials, autonomy
enabled and kill switch off. Unknown required signals require REVIEW; hard
failures BLOCK. Source and task fingerprints prevent stale authorization use.
Cadence is deterministic per platform/account: at least one hour between
reservations/execution activity and at most three per UTC day. Future windows
require reevaluation when due; this is not AI scheduling.

The existing Publish Center orchestrator/worker delegates marked tasks to the
durable G5 executor. It commits an immutable execution owner before network
work and a unique intent before each provider write stage, with fresh control
checks. Canonical task uniqueness is database-enforced on clean histories;
legacy duplicates are preserved and rejected. No transaction spans network I/O.
Operation events retain YouTube session fingerprints and final video identity,
Instagram container/media identity and Facebook start/upload/publish identity.
URLs containing session credentials are not copied into the operation ledger.

An interrupted owner is never reassigned for another upload. Durable successful
response evidence can finalize an interrupted task locally; ambiguous remote
outcomes remain REVIEW without automatic re-POST. This is local write-owner /
stage-intent protection, not a claim of remote exactly-once delivery. Existing
YouTube resumable chunk retry semantics remain within the same upload session.
Manual publishing remains a compatibility path, not a second lifecycle.

Offline evidence covers actual adapters with fake transports, all three
provider paths, policy/failure matrices, source/payload drift, crash windows,
terminal replay, 20 four-caller concurrency rounds, database unique indexes,
legacy duplicate preservation, scheduler windows and secret-safe evidence.
Existing G4-D/C/B/A, G3, G2 and publish regressions pass. No real platform,
media, AI, GA4 or GitHub workflow call was made; production DB is unchanged.
G5 is not CLOSED. Platform live proofs require separate explicit authorization.

### BREAKPOINT C — autonomous orchestration

`AUTONOMOUS_ORCHESTRATION=PARTIAL`.

The G3 policy and authorization layer is complete. The full autonomous loop is not yet closed because G4 autonomous production, G5 autonomous publishing and the later feedback-learning stages remain unfinished. The current human-gated path remains the safe development, validation, fallback, review, recovery and override mode.

`G6_OFFLINE_CERTIFIED=PASS`
`G6_LIVE=PENDING_AUTHORIZATION`

G6 reuses the existing feedback snapshot table, Data Center window aggregation,
ContentPlan providers and canonical G3 policy. A complete analytics window at
least two UTC dates old forms an account/platform cohort. Missing/conflicting
identity (including legacy content_id=platform-video fallback) is excluded.
Snapshot evidence retains the window, cohort IDs, sample size, metrics, funnel,
observational reason codes and fingerprint. A durable snapshot claim permits
one generation only; ambiguous generation stays REVIEW without automatic retry.
Plans remain preview; neither ProductionTask nor PublishTask is created.
Offline certification includes 20 rounds of four callers, failure/replay,
identity/maturity/evidence assertions, G5 through G2, r57, r44 and r16 regressions.

`G7_OFFLINE_CERTIFIED=PASS`

G7 adds a read-only `/operations/health` projection over existing tables and
delegates local evidence recovery to G5/G6. Stale RuntimeJobs/ProductionResults
and quality REVIEW are visible for authorized recovery, never blindly restarted.
Duplicate history remains intact. Provider live/credential readiness is
explicitly NOT_CHECKED by this non-network view, not inferred from configuration.
The runtime poller exposes bounded reason codes rather than provider exception
strings. Tests cover schema bootstrap, stale/restart readback, read-only health
concurrency, secret projection, kill switch, backup integrity and duplicates;
existing r47/r54/r55/r56, scheduler r29/r30/r31 and G5 recovery regressions pass.
The legacy r56 mixed-state fixture now uses a fresh job to respect canonical
one-result-per-job semantics; its rejection assertions remain unchanged.

`NEXT_MILESTONE=G8/G9 offline preparation`

G4-C provider live proof may proceed when configured and separately authorized.
G5 offline work is complete and pushed; each controlled platform proof needs
separate authorization. G6/G7 offline development and G8/G9 preparation may
continue without those live gates. No v1.0 closure is implied.

## Official roadmap

```text
G0 Genesis Alignment + Documentation Decontamination
→ G1 D10 Real GA4 Runtime
→ G2 Real AI Content Brain
→ G3 Autonomous Policy Engine
→ G4 Autonomous Production
→ G5 Autonomous Publishing
→ G6 Feedback Learning Loop
→ G7 Reliability / Recovery / Safety Seal
→ G8 Autonomous Soak Test
→ G9 v1.0 Release Hardening
```

Do not insert unrelated dashboard/UI redesigns, new platforms, duplicate production or publish frameworks, new database architecture, or Postiz work ahead of this sequence.

## v1.0 definition of done

After startup, v1.0 must automatically sync platform and landing/referral data, aggregate it in Data Center, analyze it, use real AI to generate the next ContentPlan, apply novelty/safety/quality/business policy, decide `AUTO` / `REVIEW` / `BLOCK`, and for `AUTO` approve, materialize, run, render, validate, schedule, publish, attribute and learn. It must also provide duplicate prevention, idempotency, retry and crash recovery, concurrency/stale-revision protection, rate and account controls, kill switch, review queue, structured logs, health visibility and human override.

## Canonical and legacy boundaries

Canonical runtime is `os/backend`, `os/frontend`, the Intelligence/ContentPlan/ProductionTask/VideoAsset/Publish infrastructure, Data Center and analytics runtime.

`video-factory/`, early MVP dashboards/scripts, old sync/import utilities and historical workflows are compatibility or legacy according to their subsystem documents. Postiz is **LEGACY / COMPATIBILITY**, not the formal autonomous publishing dependency. The snapshot → direct ProductionTask endpoint is a `LEGACY_INTERNAL_PATH`; new frontend and autonomous orchestration must use ContentPlan, revision, novelty, policy and approval/materialization lifecycle.

For historical short and incident status, use dated records only as history; they do not override this file.
