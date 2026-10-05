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

### Fresh-machine safe startup (offline preparation)

Use Python 3.12, Node/npm and ffprobe on PATH. Install backend requirements
from `os/backend/requirements.txt` and frontend dependencies from
`os/frontend/package.json` in a separately authorized setup session. Tests
also need pytest. Installation/network provisioning is not part of offline
certification. Do not copy another machine's credential store or production DB.

For an isolated local startup, in PowerShell at repo root:

```powershell
$env:OS_TESTING = '1'
$env:OS_DATABASE_PATH = Join-Path $env:TEMP ('rpg-startup-' + [guid]::NewGuid() + '.db')
$env:OS_DISABLE_BACKGROUND_ACCOUNT_SYNC = '1'
$env:OS_DISABLE_ANALYTICS_BACKFILL_WORKER = '1'
python -m uvicorn main:app --app-dir os/backend --host 127.0.0.1 --port 8000 --lifespan off
```

`--lifespan off` is intentional: no background runtime poller is started during
safe startup. A fresh health response may say `not_initialized`/missing tables;
that is not an error or proof of provider readiness. Use the existing UI/API
flows to initialize an authorized database; never test against production.
Run `npm run dev` from `os/frontend` separately. Bind the backend to loopback;
do not expose this single-user control plane publicly without an independently
reviewed authentication/deployment boundary.

### Operations and recovery runbook

`GET /operations/health` reads existing state without schema writes or provider
calls. It reports stale/review entities, duplicates, policy/quality counts,
data freshness, connected-account counts, controls and last completed feedback
cycle. Configuration presence is not credential validity or live readiness.
Missing signals stay unknown. Free-text provider errors and credentials are
not returned by this projection.

For an incident: disable autonomy/activate the existing kill switch, stop
workers, preserve logs with secrets redacted, and read the canonical entity
IDs/operation evidence. Do not reset a dispatch intent or reclaim an ambiguous
external-write owner. `production.runtime.health.reconcile_local_evidence()`
delegates only to existing G5 local evidence reconciliation and G6 local policy
recovery. Unknown production outcomes remain in the review projection and
require authorized existing recovery paths, not automatic redispatch.
Successful durable response evidence may finalize an already-completed remote
operation while the kill switch is on; that is not a new external write.

Backup/restore: stop application writers before maintenance. Use Python's
SQLite `Connection.backup()` into a new private destination, close both
connections, and run `PRAGMA integrity_check` on the backup. Do not copy a live
DB file while ignoring WAL/SHM. Record a SHA256 and restrictive filesystem
access for the backup (it may contain secrets). Validate restore into a new
isolated path first; verify entity counts and intent/correlation history.
Never overwrite production or delete its old copy without separate explicit
authorization. Existing duplicates must be preserved and reviewed, not removed
to make a unique index install. Schema bootstrap is idempotent; take a backup
before application upgrade. A downgrade is not a destructive schema rollback.

### Configuration and authorization checklist

- Keep credential values in the existing secure store/environment; never in Git,
  diagnostics, screenshots or shared logs. Check presence only.
- GitHub production requires the existing token/workflow configuration and an
  explicit dispatch authorization. AI configuration does not authorize paid calls.
- Each official publishing adapter requires its own account/OAuth/resource
  binding, scopes, enabled execution setting, quality PASS and publish policy.
  YouTube private and public live proofs have passed; Instagram Reel and
  Facebook Reel still require separate grants.
- GA4 uses its existing property/ADC and identity contract; do not synthesize
  events or mutate configuration to create evidence.
- Global kill switch overrides effective authorization. Raw policy AUTO alone
  neither executes production nor publishes. Cadence and account controls remain
  in the existing G5 stage.

### Soak and release gates

`python os/backend/tests/g8_autonomous_soak.py` runs only an accelerated TEMP DB,
fake-provider learning soak. It creates no real production/publish tasks and
does not prove live production, quality or publishing reliability. Its health
counters include review/stuck entities, duplicates, policy/quality outcomes,
publish intents and feedback completion; absent stages are not fake PASSes.

A future >=72h real soak requires explicit account/content/cadence/cost limits,
provider permissions, kill-switch operator and stop conditions. Track restart
behavior, duplicate writes, attribution loss, review queues, DB growth and
complete end-to-end cycles. No live soak is authorized by this runbook.
G4-D real quality and YouTube public live proofs have passed. G4-C real AI
production, Instagram/Facebook live publishing, full autonomous cycles, G6 live
feedback learning, real soak, fresh-machine deployment verification and final
release approval remain required. Do not declare v1.0 CLOSED or create a release
tag from offline certification alone.

## Boundaries

The formal media path is GitHub artifact → GitHub Pages → VideoAsset → official platform adapters. Postiz and early MVP paths remain legacy/compatibility only. New work must use the canonical ContentPlan lifecycle and existing services rather than direct snapshot-to-task shortcuts.

## Documentation reading order

1. `docs/PROJECT_STATUS.md`
2. `docs/ARCHITECTURE.md`
3. Relevant subsystem documentation
4. Source code

If supporting documentation conflicts with current status or architecture, the canonical documents win; source code wins for actual implementation behavior.
