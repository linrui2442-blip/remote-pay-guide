# Content Registry

Remote Pay Guide OS Phase 2 content asset registry.

## Purpose

The content registry provides a management layer above the existing production and publishing pipelines.

It tracks:

```
content_id
    ↓
content asset
    ↓
production status
    ↓
publish status
    ↓
platform tracking
    ↓
analytics
```

## Scope

This module does not replace or modify:

- render workflows
- artifact pipeline
- publish workflows
- Postiz
- OAuth configuration

It only provides structured asset management.

## Data Sources

Current registry fields are populated from existing project sources:

- tasks JSONL
- production metadata
- publish records
- platform status

Unknown fields are marked as `UNKNOWN` until verified from source data.

## Files

- `registry.json` - content asset records
- `schema.json` - registry structure definition
