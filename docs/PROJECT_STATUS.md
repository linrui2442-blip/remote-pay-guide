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

### BREAKPOINT C — autonomous orchestration

`AUTONOMOUS_ORCHESTRATION=PARTIAL`.

The G3 policy and authorization layer is complete. The full autonomous loop is not yet closed because G4 autonomous production, G5 autonomous publishing and the later feedback-learning stages remain unfinished. The current human-gated path remains the safe development, validation, fallback, review, recovery and override mode.

`NEXT_MILESTONE=G4 Autonomous Production`
`G4_STATUS=NOT_STARTED`
`G5_STATUS=NOT_STARTED`

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
