# Remote Pay Guide Sync Layer

## Purpose

Sync Layer is the data bridge between existing production systems and Content Registry.

It does not replace or modify:

- Render Layer
- Publish Layer
- Postiz
- OAuth
- Video generation pipeline

Current phase: interface definition only.

No automatic registry writes are performed.

---

## Architecture

```
Existing Systems
      |
      +----------------+
      |                |
      v                v
artifact_sync     publish_sync
      |                |
      +-------+--------+
              |
              v
       Content Registry
              |
              v
        analytics_sync
```

---

# 1. artifact_sync

## Responsibility

Read existing artifact information and map production assets to content_id.

Input:

```
Artifact
 ├── content_id
 ├── metadata.json
 └── video file
```

Output interface:

```json
{
  "content_id": "shortXX",
  "artifact_id": "UNKNOWN",
  "video_file": "UNKNOWN",
  "production_status": "UNKNOWN"
}
```

No registry update in current phase.

---

# 2. publish_sync

## Responsibility

Read existing publish state sources and prepare platform status mapping.

Target fields:

```
content_id
postiz_id
facebook
instagram
youtube
published_url
scheduled_time
publish_status
```

Output interface:

```json
{
  "content_id": "shortXX",
  "postiz_id": "UNKNOWN",
  "platforms": {
    "facebook": "UNKNOWN",
    "instagram": "UNKNOWN",
    "youtube": "UNKNOWN"
  }
}
```

No Postiz API modification.

---

# 3. analytics_sync

## Responsibility

Future GA4 data synchronization interface.

Current status:

```
Interface only
No API calls
No data import
```

Target mapping:

```
content_id
    ↓
platform
    ↓
views
    ↓
clicks
    ↓
conversion
```

---

## Design Principle

Sync Layer is read-oriented.

Future implementation should pull existing system data into Content Registry without changing production behavior.
