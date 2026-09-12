# Remote Pay Guide Project Status

> Concise index only. `docs/PROJECT_STATUS.md` is the canonical current status document.

## Legacy Pipeline

- short01-short10 production pipeline: completed and preserved.
- Legacy GitHub production / Postiz compatibility remains for historical compatibility.
- Formal Remote Pay Guide OS publishing must not be redesigned around Postiz.

## Remote Pay Guide OS

Remote Pay Guide OS is an AI-driven content production and growth operations control system.

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

## Completed / Verified Foundation

- GitHub Production compatibility preserved
- AI Gateway remote-production architecture preserved
- Video Asset layer implemented
- Publish Center architecture implemented
- YouTube OAuth real verified
- YouTube metadata/content sync real verified
- YouTube Analytics historical real E2E verified
- Scheduled Daily Analytics real unattended E2E verified
- Query V2 / Data Center verified
- Scheduler cross-process claim / lease / crash recovery / heartbeat verified
- Operational runtime history and health-event persistence implemented
- Test Database Isolation mainline + CI verified
- Growth / intent / conversion storage exists inside the existing Data Center
- Provider-neutral signed HMAC attribution ingestion contract locally verified
- GitHub Pages landing page live
- GA4 browser integration implemented
- `binance_referral_click` implemented
- Content → Binance referral click: **REAL GA4 E2E VERIFIED (2026-09-09)**

Real GA4 evidence verified:

```text
content_id = short04
src = yt_short04
binance_referral_click = 1
```

Binance registration/conversion attribution is deferred and is not a current blocker.

## Current Launch Requirement

The operational publishing product must support:

```text
YouTube Shorts
Instagram Reels
Facebook Reels
```

YouTube-only publishing is not sufficient for Production Trial Ready.

Current state:

- YouTube: REAL PRIVATE E2E VERIFIED
- Meta OAuth, resource discovery, and resource binding: REAL E2E VERIFIED
- Instagram: OAuth and Professional Account binding verified; official Reels publish adapter is not real E2E verified
- Facebook: OAuth and Page binding verified; official Reels publish adapter is not real E2E verified

## Current Next Development Stage

### P0 — Multi-Platform Live Publish

1. Harden the Instagram Reels official publish adapter.
2. Implement the Facebook Reels official live publish adapter.
3. Use the existing Publish Center / Registry / PublishTask system for all three.
4. Produce real publish evidence for YouTube + Instagram + Facebook.

Only after all three real paths are closed should the project be called Production Trial Ready for the user's daily publishing requirement.

### P1 — Multi-Platform Analytics + GA4 → OS

After live publishing is stable:

- close Instagram/Facebook content-sync and analytics where supported;
- import GA4 landing/referral-click signals into the existing Data Center;
- feed those business signals into Intelligence.

Do not create a second Analytics store, Query Engine, Data Center, Publish system, or OAuth system.

## Deferred / Later

- Binance registration/conversion attribution
- public Vercel/Cloudflare/HMAC relay unless justified by a real requirement
- real external AI video provider E2E
- TikTok live provider parity
- fully automatic external publishing

## Runtime Data Safety

```text
Source code:
Git repository

Runtime state:
os/database/os.db
```

The production runtime database must never be used as a test database or replaced by a fresh checkout.

See:

```text
docs/PROJECT_STATUS.md
docs/PROJECT_HANDOVER.md
docs/RUNTIME_DATA_POLICY.md
docs/OS_LOOP_GAP_AUDIT.md
docs/REMOTE_PAY_GUIDE_OS_BLUEPRINT.md
```
