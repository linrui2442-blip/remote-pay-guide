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

Scheduler coordination 使用现有 `platform_sync_state`，不新增 scheduler table 或第二套 runtime DB。候选发现可以并发，但执行前必须通过 SQLite 单事务条件 UPDATE claim `(account_id, platform, target_daily_date)`；持久 lease 的 owner 为每个 scheduler instance 的随机 ID，TTL 到期可回收。完成路径必须匹配当前 owner，因而过期的旧 process 无法覆盖已被新 owner reclaim 的状态。该层为 code/test verification；真实双进程 production-style E2E 仍是下一阶段。
