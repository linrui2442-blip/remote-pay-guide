# Remote Pay Guide — Project Status

## Canonical Current State

Remote Pay Guide OS is in active development and real-runtime validation.

Runtime state is separate from Git and must be preserved:

```text
os/database/os.db
```

Never replace, recreate, reset, destructively migrate, or use the production runtime database as a test database. See `docs/RUNTIME_DATA_POLICY.md`.

---

## Project Positioning

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

Binance registration/conversion attribution is intentionally deferred. The current business signal is the Binance referral-link click.

---

## Verified Runtime Milestones

- YouTube OAuth: REAL VERIFIED
- YouTube metadata/content sync: REAL VERIFIED
- YouTube Analytics historical backfill: FULL E2E VERIFIED
- Query V2 + Data Center gap semantics: REAL VERIFIED
- Scheduled Daily Analytics Sync: REAL UNATTENDED E2E VERIFIED
- Scheduler cross-process coordination: REAL TWO-PROCESS E2E VERIFIED
- Scheduler crash / lease recovery: REAL TWO-PROCESS E2E VERIFIED
- Scheduler lease heartbeat: REAL TWO-PROCESS E2E VERIFIED
- Operational Runtime Run History: MAINLINE + CI VERIFIED
- Crash / Recovery Lineage: MAINLINE VERIFIED
- Health Event Persistence: MAINLINE VERIFIED
- History Retention: MAINLINE VERIFIED
- Test Database Isolation: MAINLINE + CI VERIFIED
- Signed HMAC attribution ingestion contract: LOCAL CONTRACT VERIFIED
- GA4 landing-page integration: REAL ACTIVE
- Content → Binance referral click attribution: **REAL GA4 E2E VERIFIED (2026-09-09)**
- GitHub Pages → VideoAsset → Instagram prepare: CODE + TEST VERIFIED
- Meta Page publishing credential boundary: CODE + ISOLATED TEST VERIFIED
- short11 real production chain: REAL E2E VERIFIED through YouTube PUBLIC

Scheduler Operational Hardening is CLOSED. Do not add more scheduler infrastructure unless a real production failure exposes a concrete gap.

---

## short11 Production Closeout

Content: `How to Give a Client the Correct USDT Address (TRC20 vs ERC20)`

```text
Content task
→ GitHub Actions render (run 34746745765)
→ remote-pay-guide-short11 artifact
→ Quality Gate PASS
→ GitHub Pages media (promotion run 34748201584)
→ VideoAsset github_short11 ready
→ YouTube PUBLIC (jg5tSD7UETE)
```

Status:

- YouTube PUBLIC: **REAL E2E VERIFIED**
- Instagram short11: **NOT PUBLISHED**
- Instagram Graph writes: **0**
- Instagram reason: live gate / operational readiness unavailable; no Graph publish request was made.
- Facebook short11: not executed.

---

## GA4 Referral Attribution — CLOSED

The deployed GitHub Pages landing page already emits `binance_referral_click` and carries `src` + `content_id`.

Canonical future link:

```text
?src=yt_short04&content_id=short04
```

Historical links such as:

```text
?src=short04
```

remain compatible when the content identity is unambiguous.

Real production evidence observed on 2026-09-09:

```text
public GitHub Pages session
→ src=yt_short04
→ content_id=short04
→ Binance CTA clicked once
→ GA4 realtime received binance_referral_click
→ GA4 event parameter content_id = short04
→ GA4 event parameter src = yt_short04
```

Status:

```text
Content → Landing → Binance Referral Click
REAL GA4 E2E VERIFIED
```

Do not reimplement this event and do not deploy Vercel/Cloudflare merely to duplicate it.

GA4 custom-dimension registration for long-range reporting may still be checked/configured later if needed; it is not a blocker for the verified realtime delivery chain.

---

## Binance Conversion Scope

Current scope:

- Binance referral click: REAL GA4 E2E VERIFIED
- Binance registration/conversion provider: DEFERRED / NOT CURRENT BLOCKER
- Do not claim Binance registration E2E

The project should run with real traffic before deciding whether registration-level attribution is worth adding.

---

## Production Launch Requirement

The user requires the operational publishing product to support all three target platforms:

```text
YouTube Shorts
Instagram Reels
Facebook Reels
```

Therefore YouTube-only publishing is **not** sufficient for Production Trial Ready.

Current real OS publish state:

- YouTube: official AuthorizedSession/requests adapter; REAL PRIVATE E2E VERIFIED (task 12, private read-back confirmed)
- Verified 2026-09-09: account_id=1, asset_id=youtube_private_e2e_short04, task_id=12, provider video id=uEQR9PSAfUA, privacy=private; first failed task 11 remains preserved.
- Meta Account/OAuth: Historical REAL E2E VERIFIED — 2026-09-10. Current Meta operational credential is blocked by Facebook account enforcement.
- Instagram: official Graph implementation present; production live gate remains disabled; real external E2E is not verified pending a valid Meta operational identity.
- Instagram live execution will resolve a bound Page credential in memory from the stored user/account credential; Page tokens are not persisted or exposed.
- Instagram content sync: CODE + CONTRACT TEST VERIFIED; bounded Reels metadata import reuses the existing sync registry, PublishTask, VideoAsset, and D4 Page-token resolver. Real Meta read E2E is not verified.
- Facebook: Page binding was historically verified; official Reels publish adapter is not real E2E verified.
- Facebook Reels adapter: CODE + CONTRACT TEST VERIFIED; the live publish gate remains disabled by default and no external publish E2E is claimed.
- Postiz: legacy compatibility only; must not become the formal OS publish dependency

Official OS media path:

```text
GitHub Production Artifact
→ existing GitHub Pages media hosting
→ VideoAsset.asset_url
→ Publish Center
→ official platform adapter
```

Existing public GitHub Pages MP4 media is directly readable over HTTPS with
`video/mp4` responses. Postiz remains legacy compatibility only and is not a
dependency of the official OS publish path.

---

# CURRENT NEXT STEP

## P0 — D10 GA4 Runtime Activation

D9 implementation is now **CODE + CONTRACT VERIFIED**. The backend uses the
Google Analytics Data API `runReport` boundary with a default-off
`OS_GA4_DATA_INGEST_ENABLED` gate, bounded reporting dates, fail-closed
metadata checks for `customEvent:content_id` and `customEvent:src`, and
idempotent aggregate intent counts. No production ingestion has run and no
real Data API read has been performed in this phase.

Import GA4 business signals into the existing Data Center:

```text
content_id
platform/source
landing visits
Binance referral clicks
click-through rate
time window
```

No second Analytics storage and no second Query Engine.

---

## P1 — Production Line 1 Operational Automation

Operationalize the existing production line after D10 is complete or explicitly blocked. Do not build a second Production Runtime, Publish system, or scheduler infrastructure.

---

## P2 — Real Content Operations / Data Accumulation

Run the system with real content and traffic, then verify Intelligence uses referral clicks/click rate together with platform traffic/watch quality to recommend the next production strategy.

Keep task materialization and external publishing controlled until enough operational evidence exists.

---

## P3 — SUB2 + Gemini/Veo Production Line 2

SUB2 is a general AI Gateway, not a Remote Pay Guide-specific component. This lane is deferred until P0–P2 priorities permit it.

---

## External Blocker Lane — Meta Instagram/Facebook Operational Identity

Meta account connection and resource binding remain historical evidence; the current operational identity is blocked by account enforcement. Instagram/Facebook live publishing is not the current code-development P0.

---

## Later / Optional

- Binance registration/conversion attribution
- public HMAC relay/collector only if a real requirement justifies it
- real external AI video provider E2E
- TikTok live provider parity
- higher automation after real business-data evidence

---

## Current Principle

```text
Do not duplicate completed systems.
D10 GA4 Runtime Activation is the current P0.
Do not claim external E2E without real evidence.
Preserve runtime DB safety.
Keep formal OS publish on official/provider adapters, not Postiz.
```

## P1 — Production Line 1 Operational Automation

Status: **CODE + ISOLATED TEST VERIFIED**

The existing runtime now accepts the parameterized `render-short01.yml`
workflow through its allowlist (`task_file`, `content_id`, `hook`, and
`artifact_name`) and preserves `content_id` in the GitHub provider output. The
canonical completion chain remains:

```text
ProductionTask
→ GitHub workflow dispatch
→ run discovery and terminal polling
→ artifact discovery
→ Pages promotion
→ HTTPS MP4 verification
→ ProductionResult completed
→ VideoAsset ready
```

This was verified with isolated fake-client contracts. No real GitHub dispatch,
render, promotion, or publish was performed. Advanced media inspection
(1080x1920, H.264/AAC, subtitles) remains a P1 follow-up.

D10 remains **PARTIAL — waiting for post-registration GA4 content_id data**.

P1-R1 completed one real short12 render and first automatic Pages promotion.
A duplicate completion race was found and reconciled without rerendering.
Completion idempotency is now fixed and isolated-verified; short12 remains
PRODUCED / READY and has not been published.
