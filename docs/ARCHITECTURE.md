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

Blocking account sync 期间由 per-run daemon heartbeat 通过 owner-aware SQLite CAS 延长 lease。默认 heartbeat interval 从 lease TTL 推导，也可独立配置，并保持小于 TTL。heartbeat 发现 `lease_lost` 后停止续租；正在运行的 executor 自然结束，但旧 owner 不具备 success/failure persistence 权限。Process crash 会同时终止 heartbeat，其他 process 只能在最后续租产生的 expiry 后 reclaim。

该 heartbeat 已通过 network-free real two-process E2E：30 秒 TTL、5 秒 heartbeat、45 秒 executor 跨过原始 expiry，competitor 始终未执行；crash regression 证明 TTL 后仍能恢复。Runtime timing 持久化 started、finished 与 duration；health 分类覆盖 healthy、running、retrying、degraded、stuck_suspected、disabled。Stuck detection 只影响可观测性，不自动抢占 lease。

Operational Runtime History / Health Event Persistence 已完成。`runtime_operation_history` 以 `run_id` 记录 scheduler run；claim 与 history 创建保持原子性，heartbeat 只更新当前 run，终态写入使用 owner-aware compare-and-set。lease reclaim 将旧 run 标记为 `lease_expired`，并通过 `recovery_of_run_id` 保留 crash/recovery lineage。

`runtime_health_events` 只持久化实际 health transition，并对稳定状态去重。History/events 由既有 accounts read-only API 暴露，frontend 仅在 Scheduler Health 中增加 Recent Runs / Recent Health Events，不形成第二套日志中心。Retention 对 terminal history 与 health events 设置有界清理；running history 不因 retention 被删除。

上述行为已通过 network-free real-process 与 two-process E2E：competition、crash recovery、heartbeat、restart persistence 均验证。所有验证使用 `OS_TESTING=1` 与 repo 外 `OS_DATABASE_PATH`；Test Database Isolation 为 **MAINLINE + CI VERIFIED**。Scheduler Operational Hardening 已 **CLOSED**，当前工作位置为 **OS Loop Gap Audit**。ProductionRuntimePoller 与 BackgroundAccountSyncScheduler 继续作为不同 runtime worker。
