# Remote Pay Guide — Analytics

## Purpose

Analytics measures the complete acquisition path:

```
social traffic
    ↓
landing page
    ↓
user intent
    ↓
referral click
    ↓
conversion feedback
```

## Current Status

```
GA4 integration:
DONE

Event tracking:
IMPLEMENTED

Published content validation:
DONE (short01-short04)

Real traffic attribution validation:
IN PROGRESS

Revenue validation:
PENDING
```

## GA4 Integration

GA4 loading is implemented through analytics.js.

The measurement ID is configured in analytics-config.js.

Events are forwarded through the browser event layer.

## Events

Implemented events:

```
page_view
payment_type_select
payer_type_select
exchange_status_select
new_to_exchange_identified
binance_referral_click
```

## Event Flow

```
User enters Landing Page
    ↓
page_view
    ↓
payment_type_select
    ↓
payer_type_select
    ↓
exchange_status_select
    ↓
binance_referral_click
```

## Current Publishing Attribution

Active publishing platforms:

```
YouTube Shorts
Instagram Reels
Facebook Reels
```

TikTok is not currently part of the publishing workflow.

The attribution goal is:

```
content_id
    ↓
platform
    ↓
traffic source
    ↓
GA4
    ↓
binance_referral_click
```

Example:

```
short04
    ↓
youtube_short04
    ↓
GA4
    ↓
binance_referral_click
```

## Validation Status

The system has verified:

```
Content Factory
    ↓
Video Production
    ↓
Postiz Publishing
    ↓
Landing Page
    ↓
GA4 Events
```

Remaining validation:

```
Real external user
    ↓
Social platform
    ↓
Landing Page
    ↓
Intent event
    ↓
Referral conversion
```

## Goal

Identify which content generates users with real stablecoin payment intent and referral conversion.

## Current Real Validation

YouTube Analytics 7D historical backfill 已完成 FULL E2E VERIFIED：50 个真实每日 snapshots + 20 个 no-data observations（2026-08-31 至 2026-09-06，America/Los_Angeles）。Query V2 与 Data Center 已验证真实 gap（无 fake zero、无 aggregate-to-daily splitting）。Scheduled Daily Analytics Sync 目前仍仅 code/test complete，尚待独立的 unattended E2E validation。
