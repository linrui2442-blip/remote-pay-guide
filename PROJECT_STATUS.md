# Remote Pay Guide Project Status

## Current Status

Pipeline:

- short01-short10: Completed ✅

## Platform Status

Published:

- short01-short07: Published on platforms ✅

Scheduled:

- short08-short10: Scheduled in Postiz / waiting for scheduled time ⏳

Platform Operations:

- Facebook: Operational ✅
- Instagram: Operational ✅
- YouTube: Operational ✅

## Current Phase

Remote Pay Guide legacy pipeline: Maintenance / Ready for next batch

Remote Pay Guide OS: local control center, YouTube official content sync, live YouTube Analytics sync, Data Center active-tracking policy, historical outcome retention, and the unified Data Center query foundation are implemented. The next development unit is the Data Center UI built on the unified query layer, followed by scheduler-driven background sync and additional platform integrations.

## Production Pipeline

```
Render
  ↓
Artifact
  ↓
Publish Layer
  ↓
Media Hosting
  ↓
Postiz
  ↓
Social Platforms
```

The legacy GitHub production and publishing pipeline remains preserved.

## Remote Pay Guide OS Development

Current OS architecture keeps the existing production assets and aggregates them under a local control center.

Completed / implemented foundation:

- GitHub Production compatibility layer preserved
- AI Gateway remote production architecture preserved; the OS does not describe the AI Gateway path as local AI inference
- Video Asset layer
- Publish Center
- YouTube OAuth / publish path
- OS Event layer foundation
- Publish event bridge
- OS Orchestrator foundation
- Existing `os/backend/data/` confirmed as the Data Center domain; no duplicate Data Center created
- Existing Content Registry reused read-only by the OS Data Center
- Analytics storage supports traffic intelligence:
  - impressions
  - views
  - clicks / CTR
  - watch time
  - average view duration
  - average view percentage / retention
  - likes / comments count / shares
- Analytics snapshots now preserve `account_id`, platform, content/video identity, collection time, and the reporting window (`period_start` / `period_end`) required for future multi-account and time-range queries
- Raw analytics snapshot history is preserved while current funnel/performance calculations use only the newest snapshot per video/platform/account, preventing cumulative API snapshots from being double-counted
- User Intent storage implemented
- Conversion storage implemented
- Content funnel APIs implemented
- Data Center overview includes traffic, intent, referral clicks, conversions, and conversion value
- AI Intelligence receives the full growth funnel instead of judging only platform metrics
- Conversion and referral-intent signals take priority over vanity metrics when building the next production strategy
- Intelligence insight storage preserves the growth-funnel snapshot
- Production runtime circular import fixed without changing the existing production pipeline
- Analytics collector never fabricates zero traffic when an external integration is unavailable
- Platform capability runtime is implemented inside the OS Data Center and uses `os/database/os.db`
- Platform capability APIs expose supported publishing/analytics capabilities and available metric types
- Default capability metadata exists for YouTube, Instagram, Facebook, and TikTok; operational account connection remains tracked separately from capability metadata
- Existing Publish Center registry auto-discovers adapter modules instead of hard-coding the current platform list
- A future publish platform can be added as a new adapter module without editing Publish Center registry core; optional adapter capability metadata is registered into the Data Center automatically
- `GET /publish/platforms` exposes runtime adapter status together with Data Center capability metadata
- Publish Center task reads are exposed through `GET /publish/tasks` and `GET /publish/tasks/{task_id}` for the local control center
- YouTube OAuth supports explicit `publish`, `analytics`, and `full` scope profiles while keeping `publish` as the backward-compatible default
- OAuth token storage persists provider and granted scopes; legacy tokens without scope metadata are treated explicitly as upload-only
- OAuth state persists the requested scope profile and is the server-side source of truth for the initiating account
- YouTube OAuth callback no longer depends on Google returning a separate `account_id` query parameter and provides a return path to the OS after completion
- Non-secret OAuth configuration readiness is exposed through `GET /oauth/youtube/status`
- Local account management APIs are implemented and the frontend can add/list YouTube accounts
- Local frontend-to-backend CORS is configured for `localhost:5173` and `127.0.0.1:5173`, with optional `OS_FRONTEND_ORIGINS` override
- OS global proxy configuration is implemented so official platform/API traffic can use a user-configured local HTTP/Mixed proxy without hard-coding a specific proxy provider
- YouTube existing-content sync uses the official YouTube Data API and does not download or back up video files
- The current active content-sync policy is capped at the newest 10 published videos per bound account; older records already known to the OS remain in local history
- YouTube Analytics API v2 live collection is operational for per-video views, watch time, average view duration, average view percentage, likes, comments count, and shares
- YouTube watch time is normalized to seconds inside the OS
- Live collection endpoint implemented at `POST /analytics/collector/collect`
- Collector readiness can be checked per account through `GET /analytics/collector/status/{platform}?account_id=...`
- Publish Center → Analytics bridge implemented at `POST /analytics/collector/collect/publish-task/{task_id}`; it reuses the published task's platform video ID and account binding instead of duplicating publish metadata
- Account-level Analytics sync is implemented at `POST /analytics/collector/collect/account/{account_id}`
- Account Analytics sync now uses an Active Tracking Policy instead of rescanning all historical content on every request
- Active Tracking Policy:
  - newest 10 published items per account/platform are `ACTIVE`
  - older items become `HISTORICAL`
  - manually pinned older winners remain in the active Analytics query set
  - `ARCHIVED` is reserved for a later low-detail retention tier; no destructive automatic archive/prune is enabled yet
- When content leaves the active window, the OS stores a compact historical outcome summary containing traffic, watch quality, engagement, referral-click, conversion, and conversion-value fields
- Historical metrics are retained; leaving the active window does not delete old content or old outcomes
- Tracking APIs are exposed under `/data/tracking/account/{account_id}` for refresh, inspection, history, and pin/unpin operations
- A unified Data Center Query Layer is implemented at `GET /data/query`
- The unified query supports account, platform, tracking scope, sort field, sort direction, and result limit without platform-specific dashboard schemas
- Data Center Query output joins platform metrics with title/publish metadata, active/historical state, referral clicks, conversions, and conversion value
- Active-query summaries include content count, total views, watch time, weighted average view percentage, engagement, referral clicks, conversions, and conversion value
- The same query boundary is intended to feed both the Data Center UI and AI Intelligence so they do not develop separate calculation rules
- Current analytics snapshot endpoints remain available separately from raw history
- No comment-body synchronization is implemented; the previously explored comment-sync change was removed from the repository
- Local startup and OAuth boundary are documented in `os/README.md` and `os/frontend/YOUTUBE_OAUTH_CONFIG.md`

Verification:

- OS Data Center Verification passes traffic, intent, referral attribution, conversion, AI feedback, OAuth scope tracking, snapshot de-duplication, a network-free fake YouTube Analytics collector, and the Publish Center → Analytics bridge
- OS Platform Registry Verification passes dynamic adapter discovery and future-platform capability registration
- OS Frontend Verification passes the Vite production build for the current control-center UI
- OS Control Center Verification passes backend compilation, OpenAPI route visibility, account management, local CORS, Publish Center task routes, analytics collection routes, OAuth routes, and AI Gateway routes
- OS YouTube Content Sync verification covers existing-content import, account-level Analytics sync, Active Tracking Policy, historical summary retention, pinning, and the unified Data Center query layer
- Existing four publish adapters remain discoverable through the same `get_adapter()` compatibility entry point

Business feedback loop:

```
Content
  ↓
Traffic
  ↓
User Intent
  ↓
Binance Referral Conversion
  ↓
AI Intelligence
  ↓
Next Production Strategy
```

## Current Live Integration State

The local Remote Pay Guide OS has completed a real YouTube authorization and successfully used official Google/YouTube APIs through the OS-configured proxy route.

Confirmed live path:

```
Remote Pay Guide OS
  ↓
OS Network / Proxy Layer
  ↓
YouTube Data API + YouTube Analytics API
  ↓
OS SQLite Data Center
```

Current behavior:

- YouTube content metadata sync: working
- YouTube Analytics batch sync: working
- Video file download / backup: disabled by design
- Comment-body synchronization: disabled / not implemented
- Current default Analytics reporting window: most recent 28 complete calendar days, ending yesterday, unless an explicit range is supplied
- Current active observation window: newest 10 published videos per bound account/platform, plus manually pinned older items

GA4 already receives landing-page events, but OS-side GA4 report collection still requires the GA4 property/auth connection before live import can be enabled.

No secret values are stored in project documentation.

## Next Development Unit

1. Rebuild the Data Center frontend on top of `GET /data/query` instead of rendering raw analytics rows directly.
2. Add global Data Center filters for platform, account, tracking scope, time/reporting range, and sort order.
3. Show human-readable video titles, platform/account identity, reporting period, active/historical status, and business metrics instead of raw video IDs as the primary label.
4. Add scheduler-driven incremental content/Analytics synchronization after the manual flow remains stable.
5. Add future platform integrations through the existing platform registry/adapter boundaries without changing Data Center core schemas.

## Notes

short01-short10 production pipeline completed.

Platform status is tracked separately from pipeline completion.
short08-short10 will be updated to Published after scheduled posts go live.

No republishing required.
