# Registry Import Layer

Read-only import layer for Remote Pay Guide OS.

Purpose:

- Read existing project data sources.
- Prepare import reports.
- Do not modify content-registry.
- Do not change production or publish pipelines.

Sources:

1. tasks-launch02.jsonl
   - topic
   - script metadata

2. Artifact metadata
   - artifact_id
   - video_file
   - production result

3. publish-state
   - postiz_id
   - platform status
   - published_url

Import output:

registry-import/report.json
