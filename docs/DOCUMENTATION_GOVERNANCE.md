# Documentation Governance

Canonical reading order is `PROJECT_STATUS.md` → `ARCHITECTURE.md` → relevant subsystem document → source code.

`ARCHIVE_CURRENT_REQUIREMENTS_ALLOWED=false` — documents under `docs/archive/` are historical/non-canonical and must not be used to infer current requirements.

| Classification | Meaning | Examples |
|---|---|---|
| CANONICAL | Current truth or intended canonical architecture | `PROJECT_STATUS.md`, `ARCHITECTURE.md` |
| SUPPORTING | Current subsystem detail; cannot override canonical status | `ANALYTICS.md`, `CONTENT_STRATEGY.md`, `VIDEO_PRODUCTION_PIPELINE.md`, `CI_CD_VIDEO_PIPELINE.md` |
| COMPATIBILITY | Existing path retained for compatibility, not target mainline | Postiz compatibility records, older adapters |
| LEGACY | Historical implementation/path; not a design basis for new runtime | early MVP tooling, snapshot → direct ProductionTask path |
| ARCHIVE | Dated evidence, handover or incident context | dated baseline/report/handover documents |

Postiz is legacy/compatibility, not the formal autonomous publish dependency. The snapshot → direct ProductionTask route is a `LEGACY_INTERNAL_PATH`; new UI and autonomous orchestration must use ContentPlan, revision, novelty, policy and approval/materialization lifecycle.

Supporting documents should describe subsystem behavior and link current status questions to `PROJECT_STATUS.md`. Dated records remain useful for audit but must not be used to infer current requirements.
