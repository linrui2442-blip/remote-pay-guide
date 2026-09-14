# Overnight Baseline — 2026-09-14

HEAD: `c9092799798b0f0ea53c9ff652cfbcc9874b00d4`

## Architecture map

Data Center → Intelligence feedback/strategy → explicit ProductionTask → Runtime Job → ProductionResult → VideoAsset → explicit PublishTask → Analytics feedback.

## Repository truth

- CURRENT: YouTube account/runtime, GitHub production provider, ProductionTask/Result/VideoAsset, Data Center, Query Engine, Intelligence feedback bridge.
- REAL E2E: short11–short13 production; YouTube publishing has been verified for short12.
- PARTIAL: D10 GA4 real-data closeout and an ergonomic Intelligence-to-production UI.
- BLOCKED: Meta operational identity/enforcement.
- DEFERRED: TikTok.
- LEGACY: Postiz; it is not a formal OS dependency.

## Overnight plan

Add an Intelligence control surface, a structured provider-neutral ContentPlan contract, and an execution-ready bridge while preserving explicit user approval for production and publishing.

Historical handover/status documents that contradict current code, tests, or Git history are stale and must not override repository truth.
# HISTORICAL / NON-CANONICAL
#
# Preserved for historical/debugging context only. Do not use to infer current requirements, runtime readiness, architecture, roadmap or priorities.
# Current status: docs/PROJECT_STATUS.md
# Current architecture: docs/ARCHITECTURE.md
