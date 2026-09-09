# Remote Pay Guide — Project Status

## Canonical Current State

Remote Pay Guide OS is in active development and real-runtime validation.

Current repository source baseline:

```text
main
```

Runtime state is separate from Git and must be preserved:

```text
os/database/os.db
```

Do not replace, recreate, reset, migrate destructively, or use the production runtime database as a test database.

See:

```text
docs/RUNTIME_DATA_POLICY.md
```

---

## Project Positioning

Remote Pay Guide OS is an AI-driven content production and growth operations control system.

Core loop:

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
Traffic / Intent / Conversion
↓
Data Feedback
```

Current business focus is YouTube-first. Other platform adapters may exist, but they must not be treated as fully live unless their real provider integration is verified.

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
- Scheduler runtime timing / health / stuck detection: VERIFIED
- Operational Runtime Run History: MAINLINE + CI VERIFIED
- Crash / Recovery Lineage: MAINLINE VERIFIED
- Health Event Persistence: MAINLINE VERIFIED
- History Retention: MAINLINE VERIFIED
- Test Database Isolation: MAINLINE + CI VERIFIED
- Real Intent + Referral Attribution ingestion contract: LOCAL CONTRACT VERIFIED

Scheduler Operational Hardening is CLOSED. Do not continue adding scheduler infrastructure unless a new real production failure demonstrates a concrete gap.

---

## Landing Page / GA4 Attribution Reality

The public GitHub Pages landing page is already live and already uses GA4.

Current browser-side attribution capabilities already implemented:

```text
src
content_id
page_view
payment_type_select
payer_type_select
exchange_status_select
new_to_exchange_identified
binance_referral_click
```

The landing page reads `src` and `content_id` from the URL and includes them in emitted events. Clicking the Binance CTA already emits `binance_referral_click`.

Therefore, the current problem is NOT "add Binance click tracking" and NOT "deploy a public collector before any attribution can work".

The current missing proof is:

```text
Specific content
→ public GitHub Pages landing URL
→ real user/session
→ GA4 binance_referral_click
→ attribution back to that content
```

This must be validated with real GA4 evidence before being marked REAL E2E VERIFIED.

---

## Attribution Link Compatibility

GA4 attribution compatibility: **CODE + TEST VERIFIED**. New links use explicit `src` + `content_id`; historical `?src=shortXX` links recover the unambiguous content ID without changing unknown sources.

Historical posting links commonly use:

```text
?src=short04
```

New canonical links should use an explicit source plus content identifier, for example:

```text
?src=yt_short04&content_id=short04
```

Compatibility requirement:

- New links should include explicit `content_id`.
- Existing historical links must continue to work.
- If a legacy `src` unambiguously identifies a known content item, the frontend may safely recover the content identity instead of recording `content_id=unknown`.
- Do not break previously published links.

---

## HMAC Attribution Boundary

The provider-neutral signed HMAC attribution ingestion boundary remains valid and must be preserved:

```text
/attribution/intent
/attribution/conversion/{provider}
signed redirect/link
```

Its local contract is verified for signature validation, dedupe, identifier validation, privacy limits, and canonical intent/conversion writes.

However, it is NOT the current development blocker.

A separate Vercel/Cloudflare/public relay is optional future infrastructure if Remote Pay Guide later needs raw server-side attribution, richer session-level events, or a provider callback path that cannot be satisfied by GA4 reporting.

Do not deploy a new public collector merely to duplicate the GA4 click signal that already exists.

---

## Binance Conversion Scope

The current business signal being tracked is:

```text
Which content generated a Binance referral-link click?
```

The later conversion question is:

```text
Did that user actually register / convert on Binance?
```

Binance registration/conversion attribution is intentionally deferred until the project has run with real traffic long enough to justify adding it.

Current status:

- Binance referral click event: IMPLEMENTED
- Content → Binance click real GA4 attribution: PENDING REAL E2E VALIDATION
- Binance registration conversion provider/callback: DEFERRED / NOT CURRENT BLOCKER
- Do not claim Binance registration E2E

---

## Publish State

YouTube official publish architecture exists, including live adapter/readiness, OAuth upload scope checks, asset preflight, explicit task/run boundaries, and result persistence.

However, the canonical project record still does not treat a new real YouTube private upload as fully verified production evidence.

Real external upload remains an explicit user-authorized operation.

---

# CURRENT NEXT STEP

## Stage 1 — GA4 Content → Binance Referral Click Attribution Closeout

This is the immediate development/validation stage.

Do NOT re-add `binance_referral_click`; it already exists.

Required work:

1. Normalize attribution-link generation going forward to explicit `src + content_id`.
2. Preserve compatibility with historical `?src=shortXX` links.
3. Add regression tests for attribution parameters and `binance_referral_click` payload identity.
4. Perform a real public GitHub Pages → GA4 validation using one known content item.
5. Confirm the GA4 event can be attributed to that content without fabricating data.
6. Update docs only after real evidence exists.

Acceptance target:

```text
Content → Landing → Binance Referral Click
REAL GA4 E2E VERIFIED
```

---

## Stage 2 — GA4 → Remote Pay Guide OS Data Center Ingestion

After Stage 1 is proven, connect GA4 reporting into the existing OS Data Center instead of building another tracking system.

Target outcome:

```text
content_id
platform/source
landing visits
Binance referral clicks
click-through rate
↓
Data Center
↓
AI Intelligence
```

GA4 report ingestion must reuse the existing Data Center / growth / intelligence boundaries. Do not create a second analytics database or second query engine.

---

## Stage 3 — Operate and Accumulate Real Data

Let the system run long enough to accumulate real YouTube Analytics + GA4 click data before adding more infrastructure.

The project should prefer evidence from real operation over speculative platform expansion.

---

## Later / Optional

- Binance registration/conversion attribution
- Public HMAC relay/collector, only if real requirements justify it
- Real external AI video provider E2E
- Real YouTube private upload E2E with explicit user authorization
- Facebook / Instagram / TikTok full live provider parity
- Controlled Intelligence → ProductionTask automation after real business feedback is available

---

## Current Principle

```text
Do not duplicate completed systems.
Do not treat optional external infrastructure as the current blocker.
Do not claim external E2E without real evidence.
Preserve runtime DB safety.
Use real traffic data to drive the next development stage.
```
