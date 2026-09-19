# Remote Pay Guide — Analytics

## Purpose

Analytics measures the acquisition path:

```text
content traffic
→ landing page
→ user intent
→ Binance referral click
→ later conversion feedback when available
```

Current business question:

```text
Which content generated Binance referral-link clicks?
```

Binance registration/conversion attribution is a separate later question and is intentionally deferred.

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

Content → Binance referral click attribution:
REAL GA4 E2E VERIFIED (2026-09-09)

GA4 → Remote Pay Guide OS Data Center import:
REAL E2E VERIFIED.

Verified chain:

GA4 Standard Reporting
→ customEvent:content_id / customEvent:src
→ canonical attribution.ga4.sync
→ GA4DataAPIClient
→ Data Center persistence
→ Intelligence feedback snapshot

Standard Reporting evidence:

```text
content_id = short12
src = yt_short12
binance_referral_click = 1
page_view attribution = true
referral attribution = true
idempotent replay = true
```

Binance registration conversion provider:
DEFERRED / NOT CURRENT BLOCKER
```

---

## Real GA4 Referral Attribution Evidence

A real public session was executed against the deployed GitHub Pages site using the canonical attributed URL pattern.

Observed browser attribution:

```text
src = yt_short04
content_id = short04
```

The Binance CTA was clicked once.

GA4 Realtime then showed:

```text
binance_referral_click = 1
content_id = short04
src = yt_short04
```

Therefore the verified chain is:

```text
short04
→ public GitHub Pages landing page
→ real guide interaction
→ real Binance CTA click
→ GA4 binance_referral_click
→ content_id=short04
→ src=yt_short04
```

Status:

```text
Content → Landing → Binance Referral Click
REAL GA4 E2E VERIFIED
```

This evidence proves realtime event delivery and content/source attribution. GA4 custom-dimension registration for long-range reporting/Explore may still be configured or audited separately if needed; it is not required to claim the realtime E2E above.

---

## GA4 Integration

GA4 loading is implemented through `analytics.js`.

The measurement ID is configured in `analytics-config.js`.

Events are forwarded through the browser event layer.

The browser tracking layer does not require a Vercel/Cloudflare collector for the existing GA4 signal.

Do not add a second `binance_referral_click` implementation.

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

The landing page includes these attribution parameters in event payloads:

```text
src
content_id
```

---

## Attribution Link Standard

Historical links such as:

```text
?src=short04
```

remain compatible when the mapping is unambiguous.

New canonical links should use explicit source and content identity:

```text
?src=yt_short04&content_id=short04
```

Rules:

- new campaign links include explicit `content_id`;
- old links continue working;
- old videos do not need republishing merely for compatibility;
- ambiguous attribution remains unknown rather than guessed.

---

## YouTube Analytics Runtime

### Historical Analytics

YouTube Analytics 7D Historical Backfill: **FULL E2E VERIFIED**.

```text
Google OAuth
→ token refresh
→ YouTube Analytics API
→ Historical Backfill Runtime
→ analytics/no-data persistence
→ Query V2
→ Data Center
```

### Scheduled Daily Analytics

Scheduled Daily Analytics Sync: **REAL UNATTENDED E2E VERIFIED**.

```text
FastAPI lifespan
→ Background Account Sync Scheduler
→ YouTube content sync
→ YouTube Analytics reads
→ persistence
→ Query V2 / Data Center
```

No-data and aggregate-window semantics remain distinct from real zero values.

---

## Standard Reporting / OS Ingestion Evidence

The short04 evidence above remains valid as Realtime browser-to-GA4 proof. The short12 evidence is the separate Standard Reporting-to-OS canonical ingestion proof: custom dimensions persisted through reporting, canonical identity resolution succeeded, Data Center exposed page_view and referral signals, Intelligence consumed the funnel, and replay preserved the existing unique source/event_id invariant.

## Next Analytics Development

GA4 ingestion is now a verified canonical runtime capability. Future analytics work concerns operational scheduling, additional conversion sources and feedback-learning integration rather than proving base GA4 ingestion.

Future additional GA4 signals for Data Center expansion:

```text
content_id
platform/source
landing visits
Binance referral clicks
click-through rate
time window
```

Implementation must reuse the existing Data Center / Growth / Query / Intelligence boundaries and must not create a second Analytics storage system.

---

## Deferred

Binance registration/conversion attribution is deferred until real traffic volume and business need justify connecting a trusted provider callback/API or equivalent source.
# Supporting subsystem document. See docs/PROJECT_STATUS.md for current project state and priority.
