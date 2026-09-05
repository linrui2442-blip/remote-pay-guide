# Content Lifecycle State Machine

## Purpose

Lifecycle Layer calculates content progress state from existing database records.

Data flow:

```
database/content.db
        ↓
lifecycle_state.py
        ↓
lifecycle_report.json
```

Mode:

```
read_only
```

Responsibilities:

- Read existing videos data
- Read publish status data
- Read analytics metrics data
- Calculate lifecycle state

Not responsible for:

- Database writes
- Registry updates
- Publishing
- External API calls
