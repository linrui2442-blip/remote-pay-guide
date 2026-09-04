# Remote Pay Guide — Content Registry

## Purpose

This document is the single source of truth for video content production and publishing status.

It separates:

- planned content
- produced videos
- published platforms
- attribution tracking

Do not infer publishing status from tracking parameter examples.

---

# Content Plan

Planned content range:

```
short01 - short10
```

Total planned videos:

```
10
```

---

# Production Status

## Completed

### short01

Status:

```
DONE
```

---

### short02

Status:

```
DONE
```

---

### short03

Status:

```
DONE
```

---

### short04

Status:

```
DONE
```

Role:

```
Architecture validation video
```

Validated:

```
GitHub Pages public media
        ↓
Postiz
        ↓
Social platforms
```

---

# Publishing Platforms

Current active publishing workflow:

```
Facebook Reels
Instagram Reels
YouTube Shorts
```

TikTok:

```
Not currently part of publishing workflow
```

---

# Publishing Matrix

Current confirmed production:

| Content ID | Facebook | Instagram | YouTube | Status |
|---|---|---|---|---|
| short01 | Planned/Published tracking | Planned/Published tracking | Planned/Published tracking | DONE |
| short02 | Planned/Published tracking | Planned/Published tracking | Planned/Published tracking | DONE |
| short03 | Planned/Published tracking | Planned/Published tracking | Planned/Published tracking | DONE |
| short04 | Validation | Validation | Validation | DONE |

---

# Attribution Model

Each future video should map:

```
content_id
    ↓
platform
    ↓
UTM/source
    ↓
GA4
    ↓
binance_referral_click
```

Example:

```
short05
platform: youtube
content_id: short05
```

---

# Future Updates

When creating a new video, update this file with:

- content ID
- production status
- publishing platforms
- tracking parameters
- performance data
