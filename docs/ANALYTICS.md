# Remote Pay Guide — Analytics

## Purpose

Analytics measures the path:

```
social traffic
    ↓
landing page
    ↓
user intent
    ↓
referral click
```

## Current Status

```
GA4 integration:
DONE

Event tracking:
IMPLEMENTED

Real traffic validation:
PENDING

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

## Validation Required

GA4 integration does not mean the business loop is verified.

Need to confirm:

```
YouTube short04
    ↓
Profile link
    ↓
Landing Page
    ↓
GA4 realtime data
    ↓
Events received
```

## Attribution Goal

The target attribution model is:

```
short04
    ↓
yt_short04
    ↓
GA4
    ↓
binance_referral_click
```

The goal is identifying which content generates revenue.
