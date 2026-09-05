# Analytics Layer Foundation

## Purpose

Analytics Layer provides a read-only foundation for future content performance tracking.

## Data Flow

```
content_id
    ↓
platform
    ↓
metrics
    ↓
Dashboard
```

## Current Mode

```
read_only
```

## Responsibilities

- analytics source reading preparation
- structured report generation

## Not Responsible For

- API calls
- automatic synchronization
- data collection
- database writes
- registry updates
