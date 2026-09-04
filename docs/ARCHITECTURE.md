# Remote Pay Guide — Architecture

## Current Architecture

```
JSONL Tasks
    ↓
MoneyPrinterTurbo Adapter
    ↓
render_batch.py
    ↓
polish_short.py
    ↓
Finished Video
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

## Content Factory

The video production system uses predefined JSONL tasks.

Current task sources:

- tasks-launch01.jsonl
- tasks-launch02.jsonl
- tasks-short01.jsonl

Tasks contain acquisition-specific content including:

- video subject
- script
- search terms
- metadata

The render pipeline does not require an LLM to write scripts during rendering.

## Distribution Layer

Current implementation:

```
Finished MP4
    ↓
postiz_publish.py
    ↓
Postiz API
    ↓
Social Platforms
```

Current connected publishing accounts:

- Facebook ✅
- Instagram ✅
- YouTube ✅

Pending verification:

```
content_id
    ↓
post_id
    ↓
publish status
    ↓
tracking source
```

The goal is for Postiz-related publishing records to maintain:

- content_id
- video
- caption
- platform
- publish status
- tracking source

## Attribution Layer

The system needs to connect:

```
content_id
    ↓
platform distribution
    ↓
traffic source
    ↓
GA4
```

Example target flow:

```
short04
    ↓
yt_short04
    ↓
GA4
    ↓
binance_referral_click
```

## User Intent Layer

The Landing Page is not only a conversion page.

It collects user intent through:

- payment_type_select
- payer_type_select
- exchange_status_select

## Conversion Layer

Final conversion event:

```
binance_referral_click
```

## Known Constraints

- No need to redesign content strategy
- No need to rebuild Video Factory
- Validation starts from existing published assets
- short04 is the first attribution validation target

The current objective is validation, not increasing publishing volume.

The complete feedback loop is:

```
Content Factory
    ↓
Distribution
    ↓
Attribution
    ↓
User Intent
    ↓
Conversion
    ↓
Revenue Feedback
```
