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

## Current breakpoints

### BREAKPOINT A — GA4 attribution runtime

`D10_GA4_STATUS=PARTIAL`.

The `customEvent:content_id` and `customEvent:src` dimensions are registered, but post-registration attributable data has not been proven through the real GA4 Data API into the OS Data Center and Intelligence path. Do not call this CLOSED or PASS.

### Completed milestone — real AI content brain

`G2_REAL_AI_CONTENT_BRAIN=CLOSED`.

`REAL_AI_CONTENTPLAN_LIVE_E2E=PASS`. The deterministic provider remains a development/fallback implementation; the real text-AI provider and canonical directed ContentPlan preview path are verified.

### BREAKPOINT C — autonomous orchestration

`AUTONOMOUS_ORCHESTRATION=PARTIAL`.

Many automatic primitives exist, but the policy-driven data → decision → production → publish → feedback loop is not closed. The current canonical flow still requires human actions.

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
