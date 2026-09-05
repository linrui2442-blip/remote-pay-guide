# System Health Check Layer

Remote Pay Guide OS health diagnostics layer.

## Data flow

```
Project Components
        ↓
health_check.py
        ↓
health_report.json
```

## Mode

read_only

## Responsibilities

- Check required project components
- Validate database tables
- Validate dashboard and lifecycle outputs
- Generate health diagnostics report

## Not responsible for

- Writing business data
- Publishing content
- External API calls
- Automatic synchronization
