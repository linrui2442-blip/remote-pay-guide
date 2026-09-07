# Remote Pay Guide OS Repository Alignment Audit

## Audit Date and Identity

- Audit date: 2026-09-07 (Asia/Shanghai)
- Local repo: `C:\Users\L-R\Desktop\remote-pay-guide-git`
- GitHub: `https://github.com/linrui2442-blip/remote-pay-guide.git`
- Branch: `main`
- Initial local HEAD: `3b48c4902be5eae6972718a393bf25cde2c48d7b`
- Fetched `origin/main`: `4f8a85f4b55b121fbc3f282bcd28ecb85988008b`
- Initial state: behind 3, no tracked changes, no divergence
- Action: `git pull --ff-only origin main`
- Audited baseline: `4f8a85f4b55b121fbc3f282bcd28ecb85988008b`

The three fetched commits changed runtime-data policy and related documentation. No local code commit
or runtime state was discarded.

## Runtime Data Boundary

| Class | Observed paths | Finding |
|---|---|---|
| Source | `os/backend`, `os/frontend/src`, `video-factory` | Versioned source |
| Configuration | `.github/workflows`, requirements, package manifest, schemas | Versioned configuration |
| Runtime | `os/database/os.db` | Current OS state; present, untracked, **not ignored** |
| Generated | `__pycache__`, `os/frontend/node_modules`, build output | Local generated state; not ignored |
| Secrets/settings | OAuth rows and proxy settings in `os.db` | Must never enter Git or audit output |
| Historical | `content-registry/registry.json`, `database/*.py`; `database/content.db` absent | Legacy registry/migration path |

`os.db` existed at 102400 bytes. It is not tracked, but `git check-ignore -v` found no rule and the
repository has no effective `.gitignore`. This is a **HIGH safety defect**. A clean checkout restores
code, not account/OAuth/analytics/publish/asset/settings state.

Read-only schema inspection (`user_version=0`) found:

| Table | Rows | State |
|---|---:|---|
| `accounts` | 1 | accounts; legacy token columns remain |
| `oauth_tokens` | 1 | provider credential store |
| `oauth_states` | 0 | transient OAuth/PKCE |
| `analytics_metrics` | 10 | append snapshots |
| `production_tasks` | 1 | production tasks |
| `runtime_jobs` | 0 | runtime jobs |
| `video_assets` | 10 | assets/references |
| `publish_tasks` | 10 | publish/synced records |
| `platform_capabilities` | 4 | generic platform metadata |
| `network_proxy_settings` | 1 | local settings |
| `ai_gateway_settings` | 0 | remote endpoint settings |

Code lazily creates sync/tracking/growth/intelligence/result tables. Their absence in this snapshot
is not a second-store signal, but scattered lazy migration plus `user_version=0` weakens explicit
schema compatibility. `database/content.db` is absent; its scripts/workflows show a legacy generated
dashboard/migration store. The tracked registry remains a legacy lifecycle/migration input, not the
OS runtime source of truth.

## Architecture Map

```text
YouTube metadata sync ─┐
Publish result ────────┼→ analytics snapshots → Data Center Query V1
Intent/referral/value ─┘                            ↓
                                           Intelligence strategy
                                                   ↓ explicit only
ProductionTask → Scheduler → RuntimeJob → GitHub Actions | remote AI Gateway
                                      → ProductionResult → VideoAsset
                                                           ↓ explicit only
                                  PublishTask → preflight/AssetResolver
                                              → Adapter → official API
                                              → Analytics/Data feedback
```

The intended loop exists but is deliberately not fully automatic. `main.py` registers production,
runtime, results, data, AI, intelligence, publish, analytics, assets, OAuth, accounts, and settings.
The Production poller starts with FastAPI lifespan. The integrations “scheduler” is a synchronous
plan executor, not a clock/background scheduler; it has no due detector, retry schedule, or backoff.

## Architecture Red Lines

| Rule | Result | Evidence |
|---|---|---|
| Formal Publish independent of Postiz | PASS | `os/backend/publish` uses resolver/registry/adapters; YouTube uses official API |
| Legacy Postiz retained | PASS | isolated `video-factory/postiz_publish.py` and legacy workflows |
| AI Gateway remote, no local GPU | PASS | remote HTTP providers; no local inference fallback |
| YouTube Sync metadata-only | PASS | channel/playlist/video metadata and external URLs; no download |
| No comment-body sync | PASS | no comment-body API/model; only numeric `comments` |
| One analytics store | PASS | OS analytics uses `os.db`; legacy DB tooling is separate |
| One Data Query Engine | PASS | `/data/query` delegates to `query_data_center` |
| One OAuth system | WARNING | provider-neutral `oauth_tokens`; legacy token columns remain in `accounts` |
| Generic core schema | PASS | `platform` + `metrics_json`; no platform-specific view columns |
| Intelligence cannot auto-publish | PASS | refresh stores strategy; materialize creates a `created` task only |
| Runtime DB excluded from GitHub | FAIL | untracked but no ignore rule |
| Absolute path not architectural | WARNING → corrected | code is repo-relative; handover used obsolete local path |

Product drift was not found: Production, Publish, Analytics, Growth, Data Center, and Intelligence
remain present, so this is not merely a YouTube client, generator, Postiz wrapper, local-GPU system,
or analytics dashboard.

## Production, Publish, OAuth, and Sync

- Production includes task, scheduler, runtime, provider, result, and asset binding.
- GitHub production dispatches/monitors Actions through `integrations/github/client.py`.
- AI Gateway is remote HTTP only and is not-ready when an endpoint is absent.
- Publish is `VideoAsset → PublishTask → validation/preflight → Adapter → official API`.
- YouTube is `live_api`: OAuth readiness, upload scope, refresh, resumable upload, IDs/URL/status/error
  persistence are implemented. This audit did not perform a real upload, so E2E is unverified.
- Facebook/Instagram/TikTok remain placeholder/simulated and report not live.
- YouTube sync is metadata/reference-only and idempotent by known `platform_video_id`; cursor, latest-10
  active policy, manual pin, history, and archive state exist.
- OAuth is provider-oriented. No credential value was read or printed.

## Analytics, Data Center, Growth, and Intelligence

`analytics_metrics` uses INSERT history with `period_start`, `period_end`, `collected_at`, and
`metrics_json`. Provider-specific values remain in JSON; common metrics keep compatible columns.

YouTube Analytics collects a 28-complete-day window by default or a specified window. Snapshots are
window aggregates, not daily deltas. Overlapping snapshots must not be summed. Query V2 should store
or request daily buckets with explicit interval semantics and use latest-per-content-per-day
de-duplication; deltas are safe only for metrics documented as cumulative.

`GET /data/query` is Query V1. It supports account, platform, active/historical/archived/all scope,
metric selection, sorting, limits, latest metrics, referral clicks, conversions, and conversion value.
It lacks date range, time series, trend, previous-period comparison, and interval/group_by.
`DataCenter.jsx` really uses it and separately reads valid account-current analytics.

Growth schemas/APIs cover intent, referral event types, conversion/value/currency, session,
content/video, and intent linkage. This is schema/API capability, not production attribution E2E.
Intelligence reads `query_data_center`, prioritizes value → conversion → referral → intent → traffic,
and never runs or publishes a materialized task.

## Frontend/Backend and CI

Primary Data Center and Publish route/field contracts align. The dashboard's
`/analytics/metrics/current` remains valid. `api.js` fixes the base to localhost, reasonable for the
local OS but less deployable than environment configuration.

Legacy `render-launch02.yml → render_batch.py → MoneyPrinterTurbo → polish_short.py` plus JSONL and
short01-short10 compatibility remains. Legacy Postiz workflows are separate. OS workflows cover
bridge, registries, OAuth/publish readiness, sync, metrics, Data Center, account analytics, control
center, and frontend. Per-short legacy workflows duplicate the generic publish workflow but are
historical compatibility. Current remote Actions conclusions were not independently available here:
`gh` is absent and the public Actions page returned no readable run data.

## Capability Matrix

| Module | Status | Code | Tests | Real E2E | Note |
|---|---|---|---|---|---|
| Core OS | TESTED | routers/lifespan | compile PASS, contracts | not in audit | import blocked by missing deps |
| ProductionTask | TESTED | CRUD/readiness/run | smoke exists | not in audit | explicit run |
| Production Runtime | TESTED | jobs/worker/poller/results | smoke exists | not in audit | poller exists |
| GitHub Production | TESTED | Actions dispatch/monitor | bridge smoke | historical only | no dispatch in audit |
| AI Gateway | TESTED | remote HTTP lifecycle | smoke exists | PENDING | no paid endpoint call |
| Video Asset | TESTED | manager/binding/resolver | contracts | local rows | references supported |
| Platform Registry | TESTED | generic registries | smoke exists | YouTube only | others placeholder |
| Accounts | TESTED | generic CRUD/state | contracts | local row | legacy token cols |
| OAuth | TESTED | registry/state/token | smoke exists | local row | values not inspected |
| YouTube OAuth | TESTED | PKCE/scopes/refresh | smoke exists | historical only | no live auth in audit |
| YouTube Content Sync | TESTED | metadata incremental/full | fake smoke | historical only | no live call |
| Active Tracking | TESTED | latest 10/pin/history/archive | smoke PASS | not live | policy implemented |
| Analytics Storage | TESTED | snapshots + JSON | generic smoke PASS | 10 rows | window aggregates |
| YouTube Analytics | TESTED | official API client | fake smoke exists | historical only | no live call |
| Data Center Query | PARTIAL | Query V1 | V1 smoke PASS | local only | V2 missing |
| Growth | TESTED | funnel/events | contracts | PENDING | attribution unverified |
| Intent | TESTED | schema/API | contracts | PENDING | schema/API only |
| Conversion | TESTED | value/linkage | contracts | PENDING | schema/API only |
| Intelligence | TESTED | query→strategy→task | smoke PASS | PENDING | explicit only |
| Publish Center | TESTED | guarded prepare/run | contracts | PENDING | no upload in audit |
| YouTube Publish | CODE ONLY | official resumable upload | fake/contracts | PENDING | not E2E verified |
| Sync infrastructure | TESTED | registry/plan/executor/state | smoke exists | partial | plan executor |
| Background Scheduler | NOT STARTED | none for account sync | none | none | Production poller separate |
| Frontend | TESTED | pages/API | build PASS | not manually exercised | 22 modules |
| Legacy Pipeline | TESTED | workflows/scripts/JSONL | checks exist | historical | preserved |
| Postiz compatibility | TESTED | legacy only | schedule test | historical | not formal Publish |

## Verification and Test Matrix

- Git identity/status/fetch/log/diff: completed; safe fast-forward PASS.
- SQLite schema/columns/indexes/counts/version: read-only completed.
- Full source/doc search for paths, stores, proxy, Postiz, local inference, platform columns, comment
  body: completed.
- Python `compileall -q os/backend`: PASS.
- Isolated-checkout smoke PASS: `r8`, `r9`, `r11`, `r12`, `r16`.
- Other smoke scripts stopped at imports because the bundled Python lacks project dependencies
  (`requests`, Google libraries); this is not an assertion failure. Dependencies were not installed.
- Frontend `npm.cmd run build`: PASS, 22 modules. Generated output was removed.
- Backend startup/import: not run for the same missing dependencies.
- No OAuth, upload/post, production dispatch, live analytics, or paid AI call ran.
- The real runtime DB was not modified; DB-mutating tests used an isolated source snapshot.

## Risks and Drift

- **P0 Critical:** none found.
- **P1 High:** runtime/credential DB is not ignored; Query V2 could double-count overlapping windows.
- **P2 Medium:** obsolete handover path/breakpoint (corrected); weak schema versioning; incomplete local
  dependency environment.
- **P3 Low:** duplicated legacy per-short workflows; hard-coded localhost frontend API base.

Git drift was resolved. Architecture drift is low. Documentation drift was corrected. Observed runtime
tables are compatible but migration versioning is weak. Environment drift was documentation-only.

## Current Position, Breakpoint, and Plan

**Position:** single-platform OS loop plus Data Center Query V1 exists; development is at the
analytics time-series/query-contract boundary.

**Breakpoint:** `os/backend/data/query.py::query_data_center`, exposed by
`os/backend/routers/data.py::data_query`, consumed by
`os/frontend/src/pages/DataCenter.jsx::loadQuery`.

| Priority | Goal | Why/dependency | Acceptance | Do not |
|---|---|---|---|---|
| P0 | Query V2 temporal contract/minimum | Current real gap; requires window semantics | date range, daily series, comparison, interval, de-dup tests | second engine or overlap SUM |
| P1 | Protective ignore policy | DB staging risk; exact paths first | `check-ignore` matches runtime/generated/secrets | delete local state |
| P2 | Reproducible backend test environment | local dependencies absent | all network-free smoke pass isolated | implicit dependency updates |
| P3 | User-authorized private YouTube E2E | requires OAuth + ready asset | private video and persisted ID/URL/status | upload without approval |
| P4 | Publish→Analytics→Data→Intelligence E2E | depends P0/P3 | one asset reaches explicit task materialization | auto-publish |
| P5 | One real remote AI provider | depends stable loop | remote job/result/asset verified | local GPU fallback |

## Actions Performed

- Fetched and fast-forwarded `main` from `3b48c49` to `4f8a85f`.
- Preserved all local runtime/generated state and read the DB schema without credential values.
- Audited source architecture, contracts, workflows, tests, and documents.
- Ran the non-destructive verification above.
- Updated the unique handover and added this audit report.
- Source code, workflows, configuration, and runtime DB were not modified.
