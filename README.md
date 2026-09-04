# Remote Pay Guide

An overseas content acquisition MVP for people receiving USDT or USDC payments for the first time.

## Goal

Test whether stablecoin payment education content can generate attributable user intent and Binance referral conversions.

The project is not a crypto news or trading content account.

The focus is:

```
Content
  ↓
Traffic
  ↓
User Intent
  ↓
Referral Conversion
```

## Referral

Binance referral ID: `137553211`

The landing page discloses the referral relationship and reminds users to verify the exact asset and network before transferring funds.

## Current Tracking

GA4 is connected.

Tracked user behavior includes:

- `page_view`
- `payment_type_select`
- `payer_type_select`
- `exchange_status_select`
- `new_to_exchange_identified`
- `binance_referral_click`

The main measurement goal is:

```
Video
 ↓
Landing Page
 ↓
User Intent Events
 ↓
Binance Referral Click
```

## Traffic Source Tracking

Content attribution uses source parameters.

Current publishing platforms:

- YouTube Shorts
- Instagram Reels
- Facebook Reels

TikTok is not currently part of the publishing workflow.

Example source IDs:

- `yt01`
- `ig01`
- `fb01`

Each future content item should map:

```
content_id
 ↓
platform
 ↓
tracking source
 ↓
GA4
 ↓
conversion
```

## Publishing Architecture

Current workflow:

```
Content Factory
      ↓
Finished MP4
      ↓
GitHub Pages Public Media
      ↓
Postiz
      ↓
YouTube / Instagram / Facebook
      ↓
Landing Page
      ↓
GA4
      ↓
Referral Conversion
```

## Content Status

Production plan:

```
short01 - short10
```

Currently completed:

```
short01
short02
short03
short04
```

short04 is the first key architecture validation asset for:

```
Public Video URL
      ↓
Postiz
      ↓
Social Publishing
      ↓
Attribution Validation
```

## Deployment

This repository is published through GitHub Pages from the `main` branch root.
