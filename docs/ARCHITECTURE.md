# Remote Pay Guide — Architecture

## Current Architecture

```
Content Factory
    ↓
Finished MP4
    ↓
GitHub Pages Public Media
    ↓
Postiz
    ↓
Facebook / Instagram / YouTube Shorts
    ↓
Landing Page
    ↓
GA4
    ↓
Referral Conversion
```

## Content Factory

The video production system uses predefined tasks.

Production plan:

```
short01-short10
```

Completed production:

```
short01
short02
short03
short04
```

The system separates:

- planned content
- completed content

They must not be mixed.

## Distribution Layer

Current publishing architecture:

```
MP4
 ↓
Public GitHub Pages URL
 ↓
Postiz
 ↓
Social Platforms
```

Confirmed publishing platforms:

- Facebook ✅
- Instagram ✅
- YouTube Shorts ✅

TikTok is not part of the current verified distribution chain.

## short04 Validation Milestone

short04 is the first key architecture validation video.

It verified:

```
GitHub Pages public video URL
        ↓
Postiz
        ↓
External social platform publishing
```

This architecture enables future scale production without manual local upload.

## Local Operations Layer

Windows local tools manage infrastructure only:

```
Launcher
    ↓
Postiz
    ↓
Docker
    ↓
GitHub Runner
```

This layer does not define the growth architecture.

## Attribution Layer

Target tracking chain:

```
content_id
    ↓
platform
    ↓
traffic source
    ↓
GA4
    ↓
conversion
```

Example:

```
short04
    ↓
YouTube
    ↓
GA4
    ↓
binance_referral_click
```

## Conversion Layer

Final conversion event:

```
binance_referral_click
```

## Current Objective

The system is no longer proving whether publishing works.

The next objective is:

```
More content
 ↓
More traffic samples
 ↓
Better attribution data
 ↓
Better content decisions
```
