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

两条独立的真实 Analytics runtime 链均已完成验证：

### A. Historical Backfill Runtime

YouTube Analytics 7D Historical Backfill：**FULL E2E VERIFIED**。窗口为 2026-08-31 至 2026-09-06（America/Los_Angeles），结果为 50 个真实每日 snapshots + 20 个 no-data observations。Query V2 与 Data Center 已验证真实 gap（无 fake zero、无 aggregate-to-daily splitting）。

### B. Scheduled Daily Background Sync Runtime

Scheduled Daily Analytics Sync：**REAL UNATTENDED E2E VERIFIED**（2026-09-08）。FastAPI lifespan 是唯一执行触发；background scheduler 自动识别 account 1 为 due，并针对 target daily date 2026-09-06 完成真实 OAuth token refresh 和 YouTube Analytics read。10 个 eligible videos 返回 0 个 daily snapshots、10 个 `AnalyticsNoData` observations、0 failures 与 0 fake zeros，随后正确推进 persistent scheduler state。

同一轮 default aggregate window（2026-08-11 至 2026-09-07）独立写入 10 个 video aggregate rows 与 1 个 account aggregate row；这些 aggregate rows 未被当作 daily snapshots，也未拆成 daily trend points。第二次 due check 未重复运行同一 target day，same-reporting-day idempotency 已真实验证。
