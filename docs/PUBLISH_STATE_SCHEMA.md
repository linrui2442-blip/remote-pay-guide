# Publish State Tracking Schema

## Overview

`publish-state` is the Remote Pay Guide Publish Layer tracking record.

Its purpose is to connect:

```
Content Factory

↓

Distribution Layer

↓

Social Platform Post

↓

Future Attribution / GA4
```

The tracking layer provides internal attribution only.

It does **not** modify public content.

The following are not stored in public-facing content:

- content_id in video subtitles
- content_id in video frames
- content_id in public titles
- content_id in public captions

---

# File Location

Each published content item has its own state file:

```
publish-state/{content_id}.json
```

Example:

```
publish-state/short10.json
```

---

# Tracking Model

The relationship is:

```
content_id
    ↓
Publish State
    ↓
Postiz Scheduled Post
    ↓
Platform Post
```

Example:

```
short10
    ↓
Postiz post ids
    ↓
YouTube / Instagram / Facebook posts
```

---

# Schema

Example:

```json
{
  "content_id": "short10",

  "source_run_id": "33723359599",

  "media_url": ".../media/short10.mp4",

  "scheduled_at": "",

  "platforms": {

    "youtube": {
      "postiz_post_id": "",
      "status": ""
    },

    "instagram": {
      "postiz_post_id": "",
      "status": ""
    },

    "facebook": {
      "postiz_post_id": "",
      "status": ""
    }

  }
}
```

---

# Field Description

## content_id

Internal identifier for the generated content item.

Examples:

```
short08
short09
short10
```

Used to connect rendering, publishing, and attribution records.

---

## source_run_id

The GitHub Actions render run that produced the artifact.

Example:

```
33723359599
```

Used for tracing:

```
Render
 ↓
Artifact
 ↓
Publish
```

---

## media_url

Public GitHub Pages media location.

Example:

```
https://linrui2442-blip.github.io/remote-pay-guide/media/short10.mp4
```

---

## scheduled_at

The Postiz scheduled publishing time.

This preserves the publishing decision made by the Publish Layer.

---

# Platform Tracking

Each platform stores its own delivery state.

Example:

```json
"youtube": {
  "postiz_post_id": "12345",
  "status": "succeeded"
}
```

Tracked platforms:

- YouTube
- Instagram
- Facebook

---

# Design Rules

The publish-state layer is internal only.

Do not use it to modify:

- video files
- subtitles
- titles
- captions
- hashtags

Do not require Postiz public metadata fields for attribution.

The source of truth is:

```
publish-state/{content_id}.json
```
