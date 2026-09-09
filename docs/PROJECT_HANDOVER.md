# Remote Pay Guide OS — Current Project Handover

> Refreshed: 2026-09-09
>
> Repository: `linrui2442-blip/remote-pay-guide`
>
> Default branch: `main`

This is the canonical current handover. Historical commit-level detail remains in Git history and historical docs.

---

# 0. Takeover Rules

Read in this order:

```text
1. current main code
2. docs/PROJECT_STATUS.md
3. docs/PROJECT_HANDOVER.md
4. docs/OS_LOOP_GAP_AUDIT.md
5. docs/REMOTE_PAY_GUIDE_OS_BLUEPRINT.md
```

Fact priority:

```text
current main code
> docs/PROJECT_STATUS.md
> docs/PROJECT_HANDOVER.md
> Gap Audit
> Blueprint
> historical docs / old chats
```

Do not restart old phases such as Query V2, Scheduler Hardening, or mandatory Public Intent Collector deployment unless current code and current status prove a new gap.

Do not claim real E2E from synthetic/local tests.

---

# 1. Project Positioning

Remote Pay Guide OS is an AI-driven content production and growth operations control system:

```text
Data Feedback
→ AI Intelligence
→ Production Task
→ Production Execution
→ Video Asset
→ Publish
→ Traffic / Intent / Referral
→ Data Feedback
```

Current measured business signal:

```text
which content generated a Binance referral-link click?
```

Binance registration/conversion attribution is deferred until real operating data justifies it.

---

# 2. Architecture Boundaries

Preserve existing systems. Do not create replacements for:

- ProductionTask / Runtime
- VideoAsset
- PublishTask / Publish Center
- Publish Registry / Adapter architecture
- Accounts / OAuth
- Analytics storage
- Data Center / Query Engine
- AI Intelligence
- Scheduler

Formal OS publishing must use real provider/platform adapters and official/provider APIs. Postiz is legacy compatibility only.

AI Gateway remains remote-service architecture. Do not replace it with local GPU inference.

Comment-body synchronization remains forbidden. Numeric aggregate comment counts are allowed.

---

# 3. Runtime Database Safety

Runtime database:

```text
os/database/os.db
```

Source code and runtime state have separate lifecycles.

Absolute rules:

- never use the real runtime DB as a test DB;
- never reset/recreate it during smoke tests;
- never run destructive tests against repo `os/database`;
- tests use isolated repo-external databases;
- do not put runtime DB into Git.

Test Database Isolation is MAINLINE + CI VERIFIED.

---

# 4. Completed / Verified Foundation

Current verified foundation includes:

- Legacy GitHub Production compatibility
- AI Gateway architecture
- Production Runtime
- Video Asset Center
- Platform Registry
- Accounts / OAuth
- YouTube OAuth REAL VERIFIED
- YouTube metadata/content sync REAL VERIFIED
- YouTube Analytics historical FULL E2E VERIFIED
- Scheduled Daily Analytics REAL UNATTENDED E2E VERIFIED
- Query V2 / Data Center VERIFIED
- active tracking latest-10 + pinned policy
- typed no-data / gap semantics
- Scheduler cross-process claim / lease / crash recovery / heartbeat
- Operational Runtime History
- Crash / Recovery Lineage
- Health Event Persistence
- Test Database Isolation
- Guarded Publish Center
- YouTube official publish adapter/readiness architecture
- GitHub Pages landing page
- GA4 integration
- signed HMAC attribution ingestion local contract

Scheduler Operational Hardening is CLOSED.

---

# 5. GA4 Referral Attribution — REAL E2E CLOSED

The landing page already emits `binance_referral_click` and includes:

```text
src
content_id
```

New canonical link example:

```text
?src=yt_short04&content_id=short04
```

Historical links such as:

```text
?src=short04
```

remain compatible when the identity is unambiguous.

Real evidence on 2026-09-09:

```text
public GitHub Pages session
→ src=yt_short04
→ content_id=short04
→ real Binance CTA click
→ GA4 Realtime binance_referral_click = 1
→ GA4 content_id = short04
→ GA4 src = yt_short04
```

Status:

```text
Content → Landing → Binance Referral Click
REAL GA4 E2E VERIFIED
```

Do not add another Binance-click tracker.
Do not deploy Vercel/Cloudflare merely to duplicate this signal.

GA4 → OS Data Center ingestion is still not implemented and remains a later development unit.

---

# 6. Current Platform Reality

The user's actual launch requirement is three-platform publishing:

```text
YouTube Shorts
Instagram Reels
Facebook Reels
```

Therefore YouTube-only publishing is not sufficient for Production Trial Ready.

Current real OS state:

- YouTube: real OAuth/content/analytics verified; official publish adapter/readiness exists; one real new-video publish E2E still needs closeout.
- Instagram: current OS publish adapter is placeholder/simulated until real Meta integration is completed.
- Facebook: current OS publish adapter is placeholder/simulated until real Meta integration is completed.
- TikTok: not a current launch requirement.

Do not equate adapter registration with live provider readiness.

---

# 7. Current Development Breakpoint

The current launch blocker is:

```text
Multi-Platform Live Publish
```

not GA4 attribution, Query V2, Scheduler, or Binance registration conversion.

Production Trial Ready requires real publish evidence for all three target platforms.

---

# 8. Current Development Order

## P0.1 — YouTube Official Publish Real E2E Closeout

Only after explicit user authorization, perform one safe real upload, preferably private:

```text
Ready VideoAsset
→ pending PublishTask
→ explicit run
→ YouTube official API
→ platform_video_id
→ published_url
→ status=published
```

Acceptance must use truthful provider-returned identifiers/status.

Do not fall back to Postiz and do not redesign Publish Center.

## P0.2 — Meta Account / OAuth Foundation

Extend the existing provider-neutral account/OAuth architecture for Meta.

Do not create:

- second account table/system;
- second OAuth framework;
- separate Publish Center;
- hard-coded platform logic in Data Center core.

## P0.3 — Instagram Reels Official Live Publish

Implement real Instagram Reels publishing through the existing:

```text
PublishTask
→ Publish Registry
→ Adapter readiness
→ platform adapter
→ provider API
→ persisted result
```

## P0.4 — Facebook Reels Official Live Publish

Implement real Facebook Reels publishing through the same boundaries.

## P0.5 — Unified Three-Platform Publish Center

A ready VideoAsset must be publishable through the existing Publish Center to:

```text
YouTube
Instagram
Facebook
```

without duplicating PublishTask/Runtime/Registry/Data Center.

## P0.6 — Real Provider E2E for all three

Production Trial Ready requires:

```text
YouTube   → real published state
Instagram → real published state
Facebook  → real published state
```

Each path must persist truthful provider identifiers, URL/status, and error details where applicable.

---

# 9. After Three-Platform Live Publish

## P1 — Instagram/Facebook Content Sync + Analytics

Add/close real sync and analytics only through existing platform capability boundaries.

Do not add platform-specific duplicate core metric schemas.

## P1 — GA4 → OS Data Center Ingestion

Import:

```text
content_id
platform/source
landing visits
Binance referral clicks
click-through rate
time window
```

Reuse existing Data Center / Growth / Query / Intelligence. No second analytics store or query engine.

## P2 — Real Data → Intelligence → Controlled Next ProductionTask

After enough real business data accumulates, verify Intelligence uses referral-click/click-rate signals together with platform performance.

Keep external production/publish under controlled gates until operational evidence is strong.

---

# 10. Deferred / Optional

- Binance registration/conversion attribution
- public HMAC relay/collector only if a real requirement appears
- real external AI video provider E2E
- TikTok live provider parity
- higher autonomy / automatic external publish

---

# 11. External Operation Boundary

Do not perform without explicit user authorization:

- new third-party OAuth authorization
- real YouTube upload
- real Instagram/Facebook publish
- paid external AI generation
- remote content deletion/modification
- destructive runtime DB operation

Safe work that normally does not require repeated confirmation:

- read/audit source code
- non-destructive code fixes
- isolated tests
- CI fixes
- docs corrections
- normal Git commits/pushes when already authorized in the current workflow context

---

# 12. New-Window Execution Instruction

```text
You are continuing Remote Pay Guide OS development.

Repository: linrui2442-blip/remote-pay-guide
Branch: main

Read current main, then:
1. docs/PROJECT_STATUS.md
2. docs/PROJECT_HANDOVER.md
3. docs/OS_LOOP_GAP_AUDIT.md
4. docs/REMOTE_PAY_GUIDE_OS_BLUEPRINT.md

Do not rebuild existing Production, Runtime, Asset, Publish, OAuth, Analytics, Data Center, Intelligence, Scheduler or Platform Registry systems.
Do not reintroduce comment-body sync.
Do not turn AI Gateway into local GPU inference.
Do not make Postiz the formal OS publish dependency.
Do not re-add binance_referral_click; GA4 referral attribution is already REAL E2E VERIFIED.
Do not treat Binance registration conversion as a current blocker.

Current primary launch track:
MULTI-PLATFORM LIVE PUBLISH — YOUTUBE + INSTAGRAM + FACEBOOK.

First close YouTube official real publish E2E with explicit user authorization, then implement Meta account/OAuth through the existing provider-neutral architecture, then real Instagram Reels and Facebook Reels adapters, then prove real provider E2E for all three.

Preserve runtime DB safety absolutely. Tests use isolated repo-external databases only.
```

---

# 13. Current Closeout Summary

Closed:

```text
YouTube Analytics real runtime
Query V2 / Data Center
Scheduler hardening
Operational runtime history
Test DB isolation
GA4 Content → Binance Referral Click REAL E2E
```

Current launch blocker:

```text
Three-platform live publishing:
YouTube + Instagram + Facebook
```

Deferred:

```text
Binance registration conversion
mandatory public collector
TikTok
higher autonomy
```

The project is no longer in foundational architecture design. It is now in production-integration closeout for the user's real three-platform operating requirement.
