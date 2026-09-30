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

Source code is implementation truth; `PROJECT_STATUS.md` is current-state truth;
`ARCHITECTURE.md` is target/canonical architecture truth. Milestone completion,
runtime evidence and next gates belong in those documents, not a duplicated
README commit/status snapshot.

The v1 launch platforms are YouTube Shorts, Instagram Reels and Facebook Reels.
TikTok is not a v1 launch requirement. Manual mode remains a safety, validation,
fallback and override path, not the final product target.

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
