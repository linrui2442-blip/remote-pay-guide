# Remote Pay Guide

An overseas content acquisition MVP for people receiving USDT or USDC payments for the first time.

## Project Definition

Remote Pay Guide is not a crypto news, trading, or investment content account.

It is a scenario-based user acquisition system that uses cross-border payment education as the entry point to help Binance acquire new users.

The core idea:

```
Cross-border payment need
        ↓
Stablecoin payment education
        ↓
User discovers wallet / exchange needs
        ↓
Binance user conversion
```

The project focuses on people who need to receive international payments, not existing crypto traders.

## Target Users

Primary users:

- Overseas freelancers receiving international client payments
- Remote workers receiving salary through USDT / USDC
- Cross-border service providers
- Digital nomads needing global payment tools

The project does not target:

- Crypto speculation users
- Trading audiences
- Airdrop users
- Market prediction audiences

## Business Goal

The goal is to test whether payment education content can generate attributable user intent and Binance referral conversions.

The funnel is:

```
Content
  ↓
Traffic
  ↓
User Intent
  ↓
Binance Referral Conversion
```

## Content Strategy

Content focuses on solving real payment problems:

Examples:

- How freelancers can receive USDT from overseas clients
- TRC20 vs ERC20 explained for first-time users
- Common mistakes when receiving stablecoin payments
- International payment options for remote workers

The project does not compete for crypto news or trading traffic.

## Content Factory

Video production uses real stock footage from Pexels combined with AI-assisted content production.

Production workflow:

```
Content tasks (JSONL)
        ↓
AI script / content structure
        ↓
Pexels video assets
        ↓
MoneyPrinterTurbo assembly
        ↓
Voice + subtitles + editing
        ↓
polish_short.py
        ↓
Final Short MP4
```

Pexels is the visual asset source for the short-form video production pipeline.

## Referral

Binance referral ID: `137553211`

The landing page discloses the referral relationship and reminds users to verify the exact asset and network before transferring funds.

## Tracking

GA4 is connected.

Tracked user behavior includes:

- `page_view`
- `payment_type_select`
- `payer_type_select`
- `exchange_status_select`
- `new_to_exchange_identified`
- `binance_referral_click`

The main measurement goal:

```
Video
 ↓
Landing Page
 ↓
User Intent Events
 ↓
Binance Referral Click
 ↓
Conversion
```

Each content item maps through:

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

Current system:

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

## Current MVP Status

Completed:

- Content production pipeline
- Artifact pipeline
- Media hosting pipeline
- Automated publishing pipeline
- Postiz distribution
- Publish state tracking

Current batch:

```
short01 - short10
```

## Long-Term Asset

The project asset is not individual videos.

The long-term value is:

1. Automated content testing system
2. Repeatable user acquisition channel
3. Data model connecting content topics, users, and conversions

The objective is to discover:

```
Which content
 ↓
Which audience
 ↓
Which country
 ↓
Creates the highest quality Binance conversions
```

## Deployment

This repository is published through GitHub Pages from the `main` branch root.
