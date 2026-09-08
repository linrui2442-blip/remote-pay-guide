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

Scheduler Cross-process Coordination：**REAL TWO-PROCESS E2E VERIFIED ✅**（2026-09-08）。两个独立 FastAPI/Python process 同时发现相同 candidate 后，仅一个取得 SQLite atomic claim 并执行 sync；共享 active lease 可由两边的 status endpoint 观察，成功释放后同日不再执行。

Scheduler Crash / Lease Recovery：**REAL TWO-PROCESS E2E VERIFIED ✅**。lease owner 被 hard kill 后，第二个 process 在 TTL 前不执行，在 TTL 后成功 reclaim、执行并释放 lease；旧 owner 的 success/failure transition 均被 `lease_lost` 拒绝。

Scheduler Operational Health Contract：**REAL RUNTIME VERIFIED ✅**。`GET /accounts/scheduler/status` 已在两个真实 process 中验证 process health 与 persistent due/lease/retry/success/failure summary，且不暴露完整 owner UUID 或 OAuth secret/token。

Scheduler Lease Heartbeat：**REAL TWO-PROCESS E2E VERIFIED ✅**。30 秒 lease、5 秒 heartbeat 与 45 秒 synthetic executor 的两个真实 Python/FastAPI process 验证中，owner 持续续租，competitor 在原始 expiry 后仍不能 reclaim；A execution 1、B execution 0，成功后 lease 释放且 due 为 0。Process crash 后 heartbeat 停止，B 只在最后续租 TTL 到期后 reclaim，未形成永久 lease。

Scheduler Runtime Timing：**VERIFIED ✅**。started/attempted 与真实 finished time 已分离，success/failure completion time 与 duration 持久化。

Scheduler Health / Stuck Detection：**CODE + TEST VERIFIED ✅**。状态包括 healthy、running、retrying、degraded、stuck_suspected、disabled；API/UI 提供 run age、lease renewing/at-risk、last completion/duration、due/retry 等 provider-neutral 信息。

Operational Runtime Run History：**REAL PROCESS E2E VERIFIED ✅**。claim 与 history 原子创建，heartbeat 更新同一 `run_id`，success/failure/partial 完成同一记录；跨 process loser 不产生 history。

Crash / Recovery Lineage：**REAL TWO-PROCESS E2E VERIFIED ✅**。过期 owner 的 run 持久化为 `lease_expired`，reclaim run 的 `recovery_of_run_id` 指向旧 run，stale owner 无法覆盖历史终态。

Health Event Persistence：**REAL PROCESS E2E VERIFIED ✅**。健康状态转换持久化且去重，restart 后仍可通过只读 API 与 Scheduler Health UI 的 Recent Health Events 查看。

History Retention：**CODE + TEST VERIFIED ✅**。

CURRENT NEXT STEP：Operational Runtime History reconciliation 完成；等待安全 commit 推送授权。

OAuth Client runtime configuration is provided by the Windows CurrentUser secure store. The fixed bootstrap/recovery file is `%LOCALAPPDATA%\RemotePayGuide\secrets\youtube-oauth-client.json`; normal backend startup does not depend on reading that JSON. OAuth tokens remain in `os/database/os.db`.
# Runtime DB Safety

Test Database Isolation: **MAINLINE + CI VERIFIED**. Production runtime DB is never used as a test database; smoke tests use temporary isolated databases only, and destructive test operations are hard-guarded.
