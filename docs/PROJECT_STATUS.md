# Remote Pay Guide — Project Status

## Goal

Remote Pay Guide is an overseas content acquisition MVP for people receiving USDT or USDC payments for the first time.

The goal is not to build a crypto media account. The goal is to test whether stablecoin payment education content can generate attributable user intent and referral conversions.

## Current Stage

MVP infrastructure is implemented.

Current phase:

- Debug
- Validation
- Real traffic verification

The project is not currently in the idea or architecture phase.

## System Layers

Remote Pay Guide consists of:

```
Content Factory
+
Distribution Layer
+
Attribution Layer
+
User Intent Layer
+
Conversion Layer
```

## Known Constraints

- No need to redesign content strategy
- No need to rebuild Video Factory
- Validation starts from existing published assets
- short04 is the first attribution validation target

## Implemented

### Content Factory

Implemented:

```
JSONL Tasks
    ↓
MoneyPrinterTurbo Adapter
    ↓
render_batch.py
    ↓
polish_short.py
    ↓
Finished MP4
```

Content is currently pre-defined in task files, not generated in real time.

Sources include:

- tasks-launch01.jsonl
- tasks-launch02.jsonl

### Landing Page

Implemented:

- Binance referral flow
- User intent questionnaire
- GA4 integration layer

### Distribution

Partially implemented:

- Postiz API integration
- YouTube
- Instagram
- Facebook publishing support

## Published Content Validation

Verified production and publishing validation:

- short01
- short02
- short03
- short04

These assets do not need to be regenerated during validation work.

## Pending Validation

### Real Traffic Validation

Need to verify:

```
Social Platform
    ↓
Landing Page
    ↓
GA4
```

### Attribution Validation

Need to verify:

```
content_id
    ↓
platform
    ↓
GA4 source
    ↓
conversion
```

### Revenue Validation

Need to verify whether real users complete:

```
Content
    ↓
Intent
    ↓
Referral Click
```

## Current MVP Goal

Validate one complete path:

```
One video
+
One real user
+
One complete behavior path
```

Not the number of published videos.

## Next Tasks

Priority order:

1. Verify content_id → platform → GA4 → events
2. Run real short04 validation
3. Verify referral conversion events
4. Expand short05-short10 automation after validation
