# Remote Pay Guide — Project Status

## Current State

Remote Pay Guide OS is in active OS development and runtime validation.

The current repository is the source code baseline.

Runtime data is handled separately.

## Runtime Data Boundary

Active runtime database:

```text
os/database/os.db
```

Important:

- Git updates source code.
- Runtime database preserves local OS state.
- A fresh repository checkout does not contain previous runtime state.
- Do not replace the runtime database with an empty database during updates.

See:

```text
docs/RUNTIME_DATA_POLICY.md
```

## Current Principle

Code changes:

```
Git repository
```

Runtime state:

```
os/database/os.db
```

They are separate lifecycle objects.

## Historical Compatibility

Existing production, publish, OAuth, analytics and data capabilities must be extended from the current implementation.

Do not recreate completed systems from old phase documents.

## Verified Runtime Milestone

YouTube Analytics Real 7D Historical Backfill E2E：**FULL E2E VERIFIED**（YouTube account 1，2026-08-31 → 2026-09-06，America/Los_Angeles）。结果为 50 个真实每日 snapshots 与 20 个 no-data observations；Query V2 与 Data Center gap semantics 已真实验证。

Scheduled Daily Analytics Sync：**REAL UNATTENDED E2E VERIFIED ✅**（验证日期 2026-09-08）。FastAPI lifespan 自动启动 background scheduler，自动选择 due account，并通过 Windows DPAPI CurrentUser OAuth client config 与现有 refresh token 完成真实 token refresh、content sync、daily/default aggregate Analytics sync、no-data persistence、persistent scheduler state advancement，以及 Query V2 / Data Center 验证。target daily date `2026-09-06` 的 10 个 eligible videos 产生 10 个 no-data observations、0 个 daily snapshots、0 failures 与 0 fake zeros；same-day idempotency 已真实验证。

CURRENT NEXT STEP：**Scheduler Runtime Hardening / Production Observability**。下一阶段聚焦 multi-process / cross-process scheduler safety、runtime observability、duplicate-worker protection / locking 与 scheduler operational health visibility；本轮未实现这些能力。

Scheduler Cross-process Claim / Lease：**CODE + TEST VERIFIED**。`platform_sync_state` 以 SQLite 条件 UPDATE 原子 claim 同一 account/platform/reporting day；lease owner、TTL expiry/reclaim 和 owner-aware success/failure/partial release 防止两个 backend process 重复执行或 stale owner 覆盖。只读 `/accounts/scheduler/status` 与系统设置 Scheduler Health 展示运行状态、due/retry/lease 和最近成功/失败摘要。尚未进行真实双 backend process E2E。

OAuth Client runtime configuration is provided by the Windows CurrentUser secure store. The fixed bootstrap/recovery file is `%LOCALAPPDATA%\RemotePayGuide\secrets\youtube-oauth-client.json`; normal backend startup does not depend on reading that JSON. OAuth tokens remain in `os/database/os.db`.
