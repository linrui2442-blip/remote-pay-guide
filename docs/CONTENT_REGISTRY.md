# Content Registry

## Purpose

The Content Registry manages Remote Pay Guide content assets.

It tracks:

```
content_id
    ↓
content topic
    ↓
production status
    ↓
publish status
    ↓
tracking status
```

This registry is for internal AI/developer handoff and content lifecycle management.

## Registry

| content_id | topic | target user | production | publish | tracking |
|------------|-------|-------------|------------|---------|----------|
| short01 | UNKNOWN | UNKNOWN | DONE | Published | UNKNOWN |
| short02 | UNKNOWN | UNKNOWN | DONE | Published | UNKNOWN |
| short03 | UNKNOWN | UNKNOWN | DONE | Published | UNKNOWN |
| short04 | UNKNOWN | UNKNOWN | DONE | Published | UNKNOWN |
| short05 | UNKNOWN | UNKNOWN | DONE | Published | UNKNOWN |
| short06 | UNKNOWN | UNKNOWN | DONE | Published | UNKNOWN |
| short07 | UNKNOWN | UNKNOWN | DONE | Published | UNKNOWN |
| short08 | UNKNOWN | UNKNOWN | DONE | Published | UNKNOWN |
| short09 | UNKNOWN | UNKNOWN | DONE | Published | UNKNOWN |
| short10 | UNKNOWN | UNKNOWN | DONE | Published | UNKNOWN |

## Data Source Rules

Only confirmed repository data should be used to populate fields:

- task JSONL definitions
- content assets
- render metadata
- publish-state records

If a field cannot be confirmed from repository data, keep the value as `UNKNOWN`.

## Publishing Reference

Current publishing platforms:

- Facebook Reels
- Instagram Reels
- YouTube Shorts

Publishing workflow reference:

```
render
↓
artifact
↓
publish workflow
↓
media hosting
↓
Postiz
↓
platform post
```

## Batch Status

Batch:

```
short01-short10
```

Result:

```
Published
```
