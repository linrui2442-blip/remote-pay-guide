# Remote Pay Guide — Analytics

## Purpose

Analytics measures the complete acquisition path:

```text
social/content traffic
    ↓
landing page
    ↓
user intent
    ↓
Binance referral click
    ↓
conversion feedback when available
```

The current business question is:

```text
Which content generated Binance referral-link clicks?
```

Binance registration/conversion attribution is a separate later question and is intentionally deferred for now.

---

## Current Status

```text
GA4 integration:
DONE

Browser event tracking:
IMPLEMENTED

Public GitHub Pages landing page:
LIVE

Content attribution parameters:
IMPLEMENTED

Legacy attribution compatibility:
CODE + TEST VERIFIED

Binance referral click event:
IMPLEMENTED

Real content → Binance click attribution validation:
PENDING REAL GA4 E2E

GA4 → Remote Pay Guide OS Data Center import:
NOT IMPLEMENTED

Binance registration conversion provider:
DEFERRED / NOT CURRENT BLOCKER
```

---

## GA4 Integration

GA4 loading is implemented through `analytics.js`.

The measurement ID is configured in `analytics-config.js`.

Events are forwarded through the browser event layer.

The browser tracking layer does not require a Vercel/Cloudflare collector to send the existing events to GA4.

A separate signed server-side collector remains optional future infrastructure for requirements that GA4 reporting cannot satisfy.

---

## Events

Implemented events include:

```text
page_view
payment_type_select
payer_type_select
exchange_status_select
new_to_exchange_identified
binance_referral_click
```

The landing page reads attribution parameters from its URL and includes them in event payloads:

```text
src
content_id
```

---

## Referral Click Flow

Current implemented browser flow:

```text
User opens attributed landing URL
    ↓
page_view
    ↓
optional guide interactions
    ↓
user clicks Binance CTA
    ↓
binance_referral_click
    ↓
GA4
```

Do not add a second `binance_referral_click` implementation; it already exists.

---

## Attribution Link Standard

Historical published links commonly use:

```text
?src=short04
```

New canonical links should include both source and explicit content identity, for example:

```text
?src=yt_short04&content_id=short04
```

Compatibility rules:

- New campaign links should include explicit `content_id`.
- Existing historical links must continue to work.
- Do not require republishing old videos.
- Legacy `src` may be used to recover a content ID only when the mapping is unambiguous.
- Ambiguous attribution must remain unknown rather than being guessed.

---

## Current Publishing Attribution Goal

Current primary platform focus:

```text
YouTube
```

The system architecture can support more platforms later, but current real attribution validation should first close the YouTube-first path.

Target:

```text
content_id
    ↓
platform/source
    ↓
GitHub Pages landing page
    ↓
GA4
    ↓
binance_referral_click
```

Example:

```text
short04
    ↓
?src=yt_short04&content_id=short04
    ↓
GitHub Pages
    ↓
GA4
    ↓
binance_referral_click
```

---

## Real Validation State

### A. YouTube Historical Analytics

YouTube Analytics 7D Historical Backfill: **FULL E2E VERIFIED**.

Verified path:

```text
Google OAuth
→ token refresh
→ YouTube Analytics API
→ Historical Backfill Runtime
→ analytics_metrics / no-data coverage
→ Query V2
→ Data Center
```

The validated window contained real daily snapshots and typed no-data observations. Query V2 preserved gaps as unavailable rather than fabricating zero traffic.

### B. Scheduled Daily YouTube Analytics

Scheduled Daily Analytics Sync: **REAL UNATTENDED E2E VERIFIED**.

Verified path:

```text
FastAPI lifespan
→ Background Account Sync Scheduler
→ YouTube content sync
→ YouTube Analytics reads
→ analytics/no-data persistence
→ scheduler state advancement
→ Query V2 / Data Center
```

Same-reporting-day idempotency was verified, and aggregate windows remain distinct from daily snapshots.

### C. Landing Page / Binance Referral Click

Current code state:

```text
GitHub Pages: LIVE
GA4: ACTIVE
binance_referral_click event: IMPLEMENTED
src/content_id payload support: IMPLEMENTED
```

What is still missing is a recorded real E2E proof that one known content item can be traced through a real public session to a GA4 `binance_referral_click` event with the expected attribution identity.

Therefore current status is:

```text
Content → Landing → Binance Referral Click
IMPLEMENTED
REAL GA4 E2E NOT YET VERIFIED
```

---

## Current Next Step

### Stage 1 — Real GA4 Attribution Validation

Use one known content item and a canonical attributed URL.

Acceptance target:

```text
known content
→ real public GitHub Pages session
→ Binance CTA click
→ GA4 event observed
→ source/content identity confirmed
```

No fake fixtures can be used to claim REAL E2E.

### Stage 2 — GA4 → OS Data Center Ingestion

After Stage 1 is proven, connect GA4 reporting into the existing OS Data Center.

Target metrics include:

```text
landing visits
Binance referral clicks
click-through rate
content/source identity
time window
```

The implementation must reuse existing Data Center / growth / Query / Intelligence boundaries and must not create a second Analytics storage system.

---

## Deferred

Binance registration/conversion attribution is intentionally deferred until the project has accumulated enough real traffic to justify connecting a real provider callback/API or equivalent trusted source.

Do not treat this deferred item as a blocker for measuring content → Binance referral clicks.
