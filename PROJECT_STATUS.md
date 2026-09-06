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

Remote Pay Guide OS: Data Center and multi-platform runtime implemented; YouTube Analytics collector code is ready and now requires real OAuth analytics authorization before live collection can start

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
  - retention
  - likes / comments / shares
- Raw analytics snapshot history is preserved while current funnel/performance calculations use only the newest snapshot per video/platform, preventing cumulative API snapshots from being double-counted
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
- Existing Publish Center registry now auto-discovers adapter modules instead of hard-coding the four current platforms
- A future publish platform can be added as a new adapter module without editing Publish Center registry core; optional adapter capability metadata is registered into the Data Center automatically
- `GET /publish/platforms` now exposes runtime adapter status together with Data Center capability metadata
- YouTube OAuth supports explicit `publish`, `analytics`, and `full` scope profiles while keeping `publish` as the backward-compatible default
- OAuth token storage persists provider and granted scopes; legacy tokens without scope metadata are treated explicitly as upload-only
- OAuth state persists the requested scope profile and is the server-side source of truth for the initiating account
- YouTube OAuth callback no longer depends on Google returning a separate `account_id` query parameter
- YouTube Analytics API v2 client implemented for per-video views, watch time, average view duration, retention, likes, comments, and shares
- YouTube watch time is normalized to seconds inside the OS
- Live collection endpoint implemented at `POST /analytics/collector/collect`
- Collector readiness can be checked per account through `GET /analytics/collector/status/{platform}?account_id=...`
- Current analytics snapshot endpoints are available separately from raw history
- A temporary duplicate platform-capability migration under legacy `database/content.db` was removed; OS capability runtime has one storage location

Verification:

- OS Data Center Verification passes with traffic, intent, referral attribution, conversion, AI feedback, OAuth scope tracking, snapshot de-duplication, and a network-free fake YouTube Analytics collector
- OS Platform Registry Verification passes dynamic adapter discovery and future-platform capability registration
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

## Current External-Integration Breakpoint

The code path for live YouTube Analytics collection is implemented. The remaining blocker is a real Google OAuth consent/authorization step for the YouTube account.

Existing publishing credentials may still be upload-only:

- `https://www.googleapis.com/auth/youtube.upload`

YouTube Analytics collection requires:

- `https://www.googleapis.com/auth/youtube.readonly`
- `https://www.googleapis.com/auth/yt-analytics.readonly`

The backend can now initiate a deliberate full authorization using the `full` scope profile, persist the granted scopes, verify account readiness, and then call the YouTube Analytics API. No credential is silently upgraded.

Before real authorization, the Google OAuth Web Application must allow the OS callback URI being used by the local frontend (for example `http://localhost:5173/oauth/youtube/callback`). This repository does not store or change Google Console secrets/settings.

GA4 already receives landing-page events, but OS-side GA4 report collection still requires the GA4 property/auth connection before live import can be enabled.

No secret values are stored in project documentation.
No real OAuth consent flow or live analytics request was executed during this development phase.

## Notes

short01-short10 production pipeline completed.

Platform status is tracked separately from pipeline completion.
short08-short10 will be updated to Published after scheduled posts go live.

No republishing required.
