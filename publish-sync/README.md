# Publish Sync Layer

## Purpose

Publish Sync Layer is a read-only synchronization foundation for Remote Pay Guide.

Data flow:

```
publish-state
    ↓
publish_sync.py
    ↓
sync_report.json
```

## Responsibilities

- Read existing publish-state records
- Produce synchronization reports
- Preserve source data integrity

## Current Scope

This layer does NOT:

- publish content
- schedule posts
- call Postiz API
- write database records
- update Content Registry

Mode:

```
sync_mode = read_only
registry_write = false
```
