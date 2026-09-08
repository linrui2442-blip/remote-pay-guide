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

CURRENT NEXT STEP：**Scheduler Operational Hardening — Long-running Reliability & Health**。下一阶段先审计真实 scheduler 执行是否可能超过默认 1800 秒 lease，再按证据决定是否需要 renewal / heartbeat，并完善 stuck-run detection、health severity 与 restart/recovery visibility。

OAuth Client runtime configuration is provided by the Windows CurrentUser secure store. The fixed bootstrap/recovery file is `%LOCALAPPDATA%\RemotePayGuide\secrets\youtube-oauth-client.json`; normal backend startup does not depend on reading that JSON. OAuth tokens remain in `os/database/os.db`.
