# Remote Pay Guide Dashboard v1

Read-only dashboard for Remote Pay Guide OS.

## Purpose

Dashboard v1 provides visibility into existing content assets without changing production, publishing, or tracking systems.

Data sources:

- `content-registry/registry.json`
- `sync/reports/`

No:

- database
- authentication
- API
- automatic synchronization
- write operations

## Pages

### Content Overview

Shows:

- total videos
- production status
- publish status
- analytics status

### Content Detail

Shows per `content_id`:

- topic
- script_source
- video_source
- generator
- video_file
- artifact_id
- publish_status
- platforms
- analytics_status
