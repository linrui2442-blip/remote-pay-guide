# Remote Pay Guide — Architecture

## Source Code and Runtime Boundary

Remote Pay Guide OS consists of two separate layers:

```
Source Code
    ↓
Git Repository

Runtime State
    ↓
os/database/os.db
```

Git synchronization updates source code.

Runtime database contains local operating state and must be preserved separately.

## Runtime Database

Primary runtime database:

```text
os/database/os.db
```

It must not be treated as disposable build output.

## Update Model

Normal update flow:

```
Git update
    ↓
Keep runtime database
    ↓
Verify services
    ↓
Continue operation
```

A clean repository checkout is not a complete OS restoration because runtime data is separate.

## System Architecture

```
Content
 ↓
Production
 ↓
Asset
 ↓
Publish
 ↓
Traffic
 ↓
Analytics
 ↓
Intelligence
 ↓
Next Production Decision
```

Existing Production, Publish, OAuth, Analytics and Intelligence capabilities should be extended from current code.

Do not create duplicate systems based on historical documents.

## Runtime Safety Principle

Code is replaceable.

Runtime state must remain stable.

## Current Verified Analytics Boundary

Historical Analytics 链已闭合：Google OAuth → token refresh → YouTube Analytics API → Historical Backfill Runtime → analytics_metrics / no-data coverage → Query V2 → Data Center。已验证的 historical 7 日窗口包含 5 个真实 snapshot dates 与 2 个 gap dates；gap 不得伪造为零流量。

Scheduled Daily Analytics Sync 也已完成 **REAL UNATTENDED E2E VERIFIED**。FastAPI lifespan 的正常 runtime 组成包括：

```text
Production runtime poller
+ Background Account Sync Scheduler
+ Analytics Backfill Worker
```

2026-09-08 的 unattended validation 只以 FastAPI lifespan 启动 Background Account Sync Scheduler，并显式禁用 Analytics Backfill Worker 以隔离 scheduler 测试；该隔离设置不是正常生产默认配置。验证链通过 Windows DPAPI CurrentUser secure store 与 `os/database/os.db` refresh token 自动刷新 OAuth，执行 YouTube metadata/Analytics reads，并推进 no-data persistence、`platform_sync_state`、Query V2 与 Data Center。Production runtime poller 启动前确认没有 running RuntimeJob，scheduler 未创建 ProductionTask。

Scheduled daily window 与 default aggregate window 保持不同语义。Daily no-data 会保留为 unavailable gap；aggregate rows 不得拆分成 daily points。当前开发位置是 **Scheduler Runtime Hardening / Production Observability**，重点包括 multi-process / cross-process scheduler safety、duplicate-worker protection / locking、runtime observability 与 scheduler operational health visibility。

Scheduler coordination 使用现有 `platform_sync_state`，不新增 scheduler table 或第二套 runtime DB。Background Account Sync Scheduler 具备 SQLite atomic cross-process claim、owner-based lease、configurable TTL、expired lease reclaim、owner-aware compare-and-set success/failure/partial transitions、stale-owner overwrite protection、persistent scheduler health observability，以及 same-reporting-day idempotency。

这些能力已于 2026-09-08 完成真正的 two-process local runtime E2E。并发场景中两个独立 FastAPI/Python process 同时发现 candidate，只有一个获得 claim 并执行；崩溃场景中 owner 被 hard kill 后，另一个 process 只在 TTL 到期后 reclaim，旧 owner 无法覆盖新状态。`GET /accounts/scheduler/status` 的 process health 与 persistent state 在两个 process 间真实共享可见。

当前开发位置为 **Scheduler Operational Hardening — Long-running Reliability & Health**。默认 lease TTL 为 1800 秒；下一阶段先审计真实 account sync 执行时长是否可能超过 TTL，再根据证据决定是否需要 lease renewal / heartbeat，并评估 stuck-run detection、health severity/status 与 restart/recovery visibility。ProductionRuntimePoller 与 BackgroundAccountSyncScheduler 继续作为不同 runtime worker。
