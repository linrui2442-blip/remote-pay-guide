# Remote Pay Guide OS

Remote Pay Guide OS is an **AUTONOMOUS CONTENT GROWTH OS** for scenario-based stablecoin payment education and attributable user acquisition.

Target loop:

```text
Platform / website / referral data
→ Data Center → Intelligence / real AI → ContentPlan
→ policy decision → production → quality gate → publish
→ attribution → feedback learning
```

The current safe operating mode is human-gated:

```text
Intelligence → ContentPlan → Review/Edit → Novelty → Approve
→ Create ProductionTask → Run → Publish
```

This is SAFE / MANUAL MODE for development, validation, fallback, review and override. It is not the final autonomous operating model.

## Current state

Read [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for the single current-state truth source and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for canonical and target architecture.

Current main: `2e44080e3489dbd5940655cadffdde806c65cf15` (P3 CLOSED).

Current breakpoints: D10 GA4 runtime attribution (`PARTIAL`), the real AI Content Brain (`NOT_CLOSED`), and complete autonomous orchestration (`PARTIAL`).

## Runtime and development

Canonical application code is under `os/backend` and `os/frontend`. Runtime state is `os/database/os.db`; never use it as a test database. Tests must set `OS_TESTING=1` and an isolated `OS_DATABASE_PATH`.

Use the existing package/runtime instructions for local startup. Do not infer current requirements from dated reports or historical documents.

## Boundaries

The formal media path is GitHub artifact → GitHub Pages → VideoAsset → official platform adapters. Postiz and early MVP paths remain legacy/compatibility only. New work must use the canonical ContentPlan lifecycle and existing services rather than direct snapshot-to-task shortcuts.

## Documentation reading order

1. `docs/PROJECT_STATUS.md`
2. `docs/ARCHITECTURE.md`
3. Relevant subsystem documentation
4. Source code

If supporting documentation conflicts with current status or architecture, the canonical documents win; source code wins for actual implementation behavior.
