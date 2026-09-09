# Remote Pay Guide OS — Current Project Handover

> Current-state handover refreshed: 2026-09-09
>
> Repository: `linrui2442-blip/remote-pay-guide`
>
> Default branch: `main`
>
> This document intentionally describes the **current operating architecture and next development break-point**. Commit-level historical details remain available in Git history, `RUN_HISTORY.md`, and historical docs.

---

# 0. Takeover Rules

A new ChatGPT / Codex window must not redesign the project from memory or from an old phase document.

Read in this order:

```text
1. Current main branch code
2. docs/PROJECT_STATUS.md
3. docs/PROJECT_HANDOVER.md
4. docs/OS_LOOP_GAP_AUDIT.md
5. docs/REMOTE_PAY_GUIDE_OS_BLUEPRINT.md
6. Other historical docs only when needed
```

Fact priority:

```text
current main code
> docs/PROJECT_STATUS.md
> docs/PROJECT_HANDOVER.md
> docs/OS_LOOP_GAP_AUDIT.md
> Blueprint
> historical docs / old chats
```

If an older section or document says the next step is Query V2, Scheduler Hardening, or mandatory Public Intent Collector deployment, treat that as historical unless current code and `docs/PROJECT_STATUS.md` confirm it.

User workflow preference:

- execute rather than repeatedly ask for permission;
- inspect code, fix, test, commit, and check CI directly when safe;
- stop only for real third-party authorization, paid external generation, real public publishing, destructive operations, or credentials that truly require the user;
- do not claim external E2E from synthetic tests.

---

# 1. Project Positioning

Remote Pay Guide OS is **not** a single video generator and **not** a YouTube client.

It is an AI-driven content production and growth operations control system:

```text
Data Feedback
↓
AI Intelligence
↓
Production Task
↓
Production Execution
↓
Video Asset
↓
Publish
↓
Traffic / Intent / Referral / Conversion
↓
Data Feedback
```

Current practical business loop is:

```text
Content
↓
YouTube traffic / engagement
↓
Landing page
↓
User intent
↓
Binance referral-link click
↓
AI Intelligence
↓
Next production strategy
```

A later optional business loop may add verified Binance registration/conversion attribution when a real provider/API/callback or equivalent trusted source is available and worth integrating.

Do not make Binance registration attribution a blocker for measuring referral-link clicks now.

---

# 2. Architecture Boundaries That Must Not Drift

## 2.1 Dual Production Architecture

### GitHub Production Line

Existing legacy production remains compatible:

```text
Production Task
↓
GitHub Provider
↓
GitHub Actions
↓
Existing Render Pipeline
↓
Production Result
↓
Video Asset
```

Historical `short01-short10` assets/workflows must remain compatible.

### AI Remote / AI Gateway Production Line

Correct architecture:

```text
Production Task
↓
AI Gateway Provider
↓
AI API Relay / Gateway
↓
External AI Video Service
↓
Production Result
```

Forbidden reinterpretation:

```text
PC
↓
local GPU
↓
local AI model
↓
generate video
```

The user's PC is the OS control center, not a local AI inference server.

Use the terms:

- `AI Remote Production Line`
- `AI Gateway Production Line`

---

# 3. Source Code and Runtime Data Are Separate

Source code:

```text
Git repository
```

Runtime state:

```text
os/database/os.db
```

The runtime database is not disposable build output.

Rules:

- Git updates source code.
- A fresh checkout does not restore runtime state.
- Never replace the real runtime DB with an empty test DB.
- Never use the real runtime DB as a smoke-test database.
- Do not run destructive migrations/tests against the production path.

Test Database Isolation is **MAINLINE + CI VERIFIED**:

```text
OS_TESTING=1
+ explicit repo-external OS_DATABASE_PATH
```

Production paths and paths under repository `os/database` are rejected in test mode before destructive access.

See `docs/RUNTIME_DATA_POLICY.md`.

---

# 4. Backend / Frontend Runtime

Backend entry:

```text
os/backend/main.py
```

Normal local backend:

```powershell
python -m uvicorn main:app --app-dir os/backend --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd os/frontend
npm.cmd run dev
```

Default frontend:

```text
http://localhost:5173
```

Default backend:

```text
http://127.0.0.1:8000
```

Backend code changes normally require backend restart. Vite frontend changes generally require refresh.

---

# 5. Network / Proxy

The OS already has explicit network/proxy configuration:

- `os/backend/config/network.py`
- `os/backend/integrations/google_transport.py`
- Settings API/UI

Modes include manual/system/disabled.

Do not hard-code a specific local proxy port. Google/YouTube calls should reuse the existing transport layer.

---

# 6. Platform Status

Publish Registry:

```text
os/backend/publish/registry.py
```

Adapters are discovered dynamically.

Current real state:

- YouTube: real OAuth/content/analytics path verified; official publish adapter exists.
- Facebook: placeholder/simulated in current OS publish architecture unless later real provider work proves otherwise.
- Instagram: placeholder/simulated unless later proven live.
- TikTok: placeholder/simulated unless later proven live.

Do not equate "adapter registered" with "real platform integration complete".

Current development strategy is **YouTube-first**. Close the real single-platform business loop before expanding platform breadth.

---

# 7. OAuth / YouTube Account

Existing OAuth stack must be extended, not replaced:

- `os/backend/oauth/`
- `os/backend/accounts/`

YouTube OAuth capabilities already cover:

- PKCE
- one-time state consumption
- redirect `code_verifier`
- scope handling
- token refresh
- read / analytics / upload scopes
- provider-neutral callback architecture

OAuth client configuration and OAuth tokens are separate:

```text
OAuth client config
→ Windows CurrentUser secure store

OAuth tokens
→ os/database/os.db
```

Recovery JSON logical path:

```text
%LOCALAPPDATA%\RemotePayGuide\secrets\youtube-oauth-client.json
```

The recovery JSON is bootstrap/recovery only. Normal backend operation should use the secure store.

Never write OAuth secrets into Git, docs, frontend, logs, or public APIs.

---

# 8. YouTube Content Sync

YouTube existing-content sync is already implemented and real-verified.

Rules:

- use YouTube Data API metadata/reference;
- do not download YouTube videos to the PC;
- dedupe by platform video identity;
- preserve latest-10 + pinned active tracking policy;
- preserve older historical content/outcomes;
- synced-from-YouTube remote assets must not be treated as local source assets for republishing.

Do not rebuild content sync.

---

# 9. Comment Boundary

Comment-body synchronization was explicitly removed and must not return.

Do not add:

- commentThreads body sync
- comment text storage
- comment samples
- audience-comment NLP pipeline

Numeric YouTube Analytics `comments` counts are allowed because they are aggregate metrics, not comment-body synchronization.

---

# 10. Analytics / Data Center

There is one canonical OS Data Center and one Query Engine.

Primary runtime domain:

```text
os/backend/data/
os/backend/analytics/
os/database/os.db
```

Do not create a second analytics database, second Data Center, or platform-specific core metric schema.

Verified YouTube Analytics capabilities include:

- real historical daily backfill
- typed no-data observations
- aggregate-window semantics
- Query V2 date ranges
- daily trend gaps without fake zeros
- previous-period comparison
- scheduled daily sync
- account-level aggregate collection

Historical 7-day real E2E and scheduled unattended real E2E are complete.

Important semantics:

- no provider data ≠ zero traffic;
- aggregate rows must not be split into fake daily rows;
- overlapping aggregate windows must not be summed as independent daily values.

---

# 11. Scheduler / Runtime Hardening

Scheduler Operational Hardening is **CLOSED**.

Completed capabilities include:

- SQLite atomic cross-process claim
- owner lease
- TTL expiry / reclaim
- stale-owner CAS protection
- lease heartbeat
- long-running execution protection
- crash recovery lineage
- exact started/finished/duration persistence
- health states / stuck detection
- runtime run history
- health-event persistence
- retention
- restart persistence
- real two-process synthetic E2E
- CI verification

Do not continue expanding scheduler infrastructure unless a new real production failure exposes a concrete scheduler gap.

---

# 12. Production / VideoAsset / Publish

Existing domains:

```text
os/backend/production/
os/backend/assets/
os/backend/publish/
```

ProductionTask, RuntimeJob, ProductionResult, VideoAsset and PublishTask already exist.

Formal OS publishing must use platform adapters / official APIs. Postiz is legacy compatibility only.

Important Publish safety boundary:

```text
create PublishTask
≠ upload
```

External upload requires explicit run.

The YouTube official adapter, OAuth upload-scope preflight, asset resolution and result persistence exist, but canonical project status still does **not** claim that a new real YouTube private upload has been fully closed out as production E2E.

A real external upload must wait for explicit user authorization.

---

# 13. AI Intelligence

Existing Intelligence domain:

```text
os/backend/intelligence/
```

Capabilities include:

- feedback bridge
- insight generation
- strategy recommendation
- task generator
- explicit ProductionTask materialization

Current safety contract:

```text
recommendation
≠ automatic ProductionTask execution
≠ automatic external publish
```

Real business feedback should be strengthened before increasing autonomy.

---

# 14. Landing Page and GA4 — Current Reality

The public landing page is already hosted on GitHub Pages.

The site already loads GA4 through:

```text
analytics-config.js
analytics.js
app.js
```

Implemented browser events include:

```text
page_view
payment_type_select
payer_type_select
exchange_status_select
new_to_exchange_identified
binance_referral_click
```

`app.js` reads URL attribution fields:

```text
src
content_id
```

and includes them in emitted event payloads.

The Binance CTA already emits:

```text
binance_referral_click
```

Therefore **do not add a second Binance-click tracking implementation**.

---

# 15. Attribution Link Standard

Historical posting links often use:

```text
?src=short04
```

New canonical links should use explicit source and content identity, for example:

```text
?src=yt_short04&content_id=short04
```

Compatibility rules:

- new links should include explicit `content_id`;
- existing historical links must keep working;
- do not require old videos to be republished;
- a legacy `src` may recover content identity only when mapping is unambiguous;
- ambiguous attribution remains unknown instead of guessed.

This is a compatibility/validation task, not a new tracking-system build.

---

# 16. Signed HMAC Attribution Boundary

Commit `b4022832dfc47721ff6ed8710ba052f940d00974` added a provider-neutral trusted attribution ingestion boundary.

Existing local contract includes:

```text
/attribution/intent
/attribution/conversion/{provider}
signed redirect/link
HMAC verification
dedupe
identifier validation
privacy limits
provider-neutral conversion adapter boundary
```

Local r32 contract is verified.

This capability must be preserved, but **public relay deployment is not the current blocker**.

A Vercel/Cloudflare/public collector is optional future infrastructure if the project later needs:

- first-party server-side raw events independent of GA4;
- trusted session-level attribution;
- a provider callback that requires a public receiver;
- data not available through GA4 reporting.

Do not deploy infrastructure merely to duplicate an existing GA4 `binance_referral_click` signal.

---

# 17. Binance Click vs Binance Registration Conversion

Keep these separate:

```text
A. Which content produced a Binance referral-link click?
B. Did that user later register / convert on Binance?
```

Current scope:

- A = current priority.
- B = intentionally deferred until the project has accumulated enough real traffic to justify provider integration.

Current truth:

```text
Binance referral click browser event:
IMPLEMENTED

Content → Binance click real GA4 attribution:
NOT YET REAL E2E VERIFIED

Binance registration conversion provider:
DEFERRED / NOT CURRENT BLOCKER
```

Never claim Binance registration E2E without a real external conversion source.

---

# 18. Current Development Breakpoint

The old Query V1/Query V2 and Scheduler Hardening breakpoints are historical and completed.

The current engineering breakpoint is:

```text
GitHub Pages + GA4 click tracking already exist
↓
need real per-content attribution proof
↓
then import GA4 business signals into the OS Data Center
```

Immediate unresolved proof:

```text
known content
→ attributed public landing URL
→ real public session
→ Binance CTA click
→ GA4 binance_referral_click
→ same source/content identity confirmed
```

This is **not** yet REAL E2E until observed in real GA4 data.

---

# 19. Current Development Order

## P0 — GA4 Content → Binance Referral Click Attribution Closeout

Do not reimplement the event.

Work:

1. Standardize future links to explicit `src + content_id`.
2. Preserve historical `?src=shortXX` compatibility.
3. Add regression coverage for attribution fields and `binance_referral_click` payload identity.
4. Use one known content item for a real public GitHub Pages session.
5. Click the actual Binance CTA.
6. Verify the GA4 event and content/source identity.
7. Only then mark:

```text
Content → Landing → Binance Referral Click
REAL GA4 E2E VERIFIED
```

## P0 — GA4 → OS Data Center Ingestion

After real attribution is proven, connect GA4 reporting into the existing OS Data Center.

Required target signals:

```text
content_id
platform/source
landing visits
Binance referral clicks
click-through rate
time window
```

Implementation rules:

- reuse existing Data Center / growth / Query / Intelligence domains;
- no second Analytics store;
- no second Query Engine;
- preserve unavailable/no-data semantics;
- no fake zero values;
- provider-neutral design where practical.

## P1 — Operate and Accumulate Real Data

Let scheduled YouTube Analytics and GA4 attribution accumulate real data.

Prefer real operational evidence over speculative infrastructure.

## P1 — Real YouTube Publish Closeout

Only after explicit user authorization:

```text
ready local VideoAsset
→ pending PublishTask
→ explicit run
→ real YouTube private upload
→ platform_video_id
→ published_url
→ persisted published state
→ later Analytics observation
```

## P1 — Real Feedback → Controlled Next ProductionTask

After enough real click data is imported into the OS, verify that Intelligence uses referral clicks/click rate alongside YouTube traffic/watch quality and produces a sensible next strategy.

Keep ProductionTask materialization/execution under a controlled safety gate.

## Later / Optional

- Binance registration conversion attribution
- public HMAC relay/collector if justified
- real external AI video provider E2E
- Facebook / Instagram / TikTok real provider parity
- higher automation only after real business-data evidence

---

# 20. What Not to Build Now

Do not build:

- another `binance_referral_click` tracker;
- a mandatory Vercel/Cloudflare collector;
- Binance registration conversion before it is needed;
- another Scheduler;
- another Data Center;
- another Analytics storage layer;
- another Query Engine;
- another OAuth system;
- comment-body synchronization;
- local GPU AI fallback;
- Postiz as the formal OS publish dependency;
- automatic external publishing before real feedback is stable.

---

# 21. External Operation Boundary

Do not perform without explicit user authorization:

- new OAuth authorization
- real YouTube upload
- real Facebook/Instagram/TikTok publish
- paid external AI generation
- deletion/modification of remote content
- destructive runtime DB operation

Safe work that normally does not require repeated confirmation:

- read/audit source code
- non-destructive code fixes
- isolated tests
- CI fixes
- docs corrections
- Git commits/pushes when already authorized by the workflow context
- read-only runtime verification

---

# 22. New-Window Execution Instruction

```text
You are continuing Remote Pay Guide OS development.

Repository: linrui2442-blip/remote-pay-guide
Branch: main

Read current main first, then:
1. docs/PROJECT_STATUS.md
2. docs/PROJECT_HANDOVER.md
3. docs/OS_LOOP_GAP_AUDIT.md
4. docs/REMOTE_PAY_GUIDE_OS_BLUEPRINT.md

Do not rebuild existing Production, Runtime, Asset, Publish, OAuth, Analytics, Data Center, Intelligence, Scheduler or Platform Registry systems.
Do not reintroduce comment-body sync.
Do not turn AI Gateway into local GPU inference.
Do not make Postiz the formal OS publish dependency.
Do not treat a public Vercel/Cloudflare collector as mandatory for the current click-attribution goal.
Do not re-add binance_referral_click; it already exists in the landing page.

Current next stage:
GA4 Content → Binance Referral Click Attribution Closeout.

First normalize attribution-link compatibility, add regression coverage, and prove one real GitHub Pages → GA4 binance_referral_click event can be attributed to one known content item.

After that, implement GA4 → existing OS Data Center ingestion for landing visits, referral clicks and click-through rate.

Binance registration conversion attribution is deferred and is not a current blocker.

Preserve production runtime DB safety absolutely. Tests must use isolated repo-external databases only.

Enter execution mode. Ask the user only for truly external authorization or information that cannot be resolved from code/runtime state.
```

---

# 23. Current Closeout Summary

Completed foundation:

```text
Legacy GitHub Production compatibility
Production Runtime
AI Gateway architecture
Video Asset Center
Platform Registry
Accounts / OAuth
YouTube Content Sync
YouTube Analytics real E2E
Query V2 / Data Center
Scheduled Daily Analytics
Scheduler cross-process hardening
Operational Runtime History
Crash / Recovery Lineage
Health Event Persistence
Test Database Isolation
Guarded Publish Center
YouTube Official Publish Adapter
GA4 landing-page tracking
Signed local attribution ingestion contract
```

Current focus:

```text
REAL per-content GA4 Binance referral-click attribution
↓
GA4 business-signal ingestion into existing OS Data Center
↓
real-data-driven Intelligence
```

Deferred:

```text
Binance registration conversion attribution
mandatory public collector infrastructure
multi-platform expansion
higher autonomy
```

The project is no longer in foundational architecture design. It is entering the stage where existing systems must consume **real business signals** and prove the operating loop with real data.
