# Remote Pay Guide OS Loop Gap Audit

审计基线：`9f2f33f537eddee5377a8c31e2aefc03716a2b95`（只读审计，2026-09-08）。成熟度只按真实 writer、reader、运行时和测试证据判断；synthetic fixture 不等同于真实外部 E2E。

## Scheduler Closeout

Scheduler Operational Hardening、Operational Runtime History、Crash/Recovery Lineage、Health Event Persistence、History Retention 均为 **MAINLINE + CI VERIFIED**（其中 E2E 证据是 network-free synthetic real-process/two-process，不宣称长期生产运行）。Test Database Isolation 为 **MAINLINE + CI VERIFIED**。

## Gap Matrix

| Stage | Current maturity | Real data source | Writer | Reader | Automation | External dependency | E2E status | Main gap | Priority |
|---|---|---|---|---|---|---|---|---|---|
| Content Data | REAL E2E VERIFIED | YouTube Data API v3 metadata; local publish/task metadata | `integrations/youtube.py`, `assets/manager.py`, `publish/manager.py`, `data/tracking.py` | Data Center query, tracking APIs/UI | Scheduler content sync; latest-10 + pinned | YouTube OAuth/Data API | Real content/analytics flows; CI synthetic doubles | No provider-wide reconciliation/deletion history guarantee | P1 |
| Analytics | REAL E2E VERIFIED | YouTube Analytics API daily/aggregate rows and typed no-data | `analytics/collector.py`, `analytics/manager.py`, backfill and scheduler | Query V2, Data Center, analytics routers | Scheduled daily + historical backfill | YouTube OAuth/Analytics API | Historical 7D real E2E; Query V2/gap semantics verified | Limited provider coverage; no independent attribution | P1 |
| AI Intelligence | CODE + TEST VERIFIED | Query V2 metrics plus local funnel records; deterministic strategy rules; optional remote AI Gateway | `intelligence/feedback_bridge.py`, `insights.py`; `analyzer.py` calls gateway only when requested | Intelligence routers/UI, feedback snapshots | Refresh is explicit; no autonomous cycle | Optional configured remote AI gateway | Synthetic feedback/strategy tests; no real model E2E | No continuously running model decision or production outcome learning | P0 |
| ProductionTask | CODE + TEST VERIFIED | Strategy snapshot or manual API input | `production/tasks/manager.py`; `task_generator.py`; explicit materialize endpoint | Production task APIs/UI | Scheduler does not create tasks | None for local persistence | Contract tests; task creation is local | AI → automatic task creation is absent; materialization is manual | P0 |
| Production Runtime | CODE + TEST VERIFIED | Local task/runtime records; GitHub/AI provider adapters | runtime manager/worker/orchestrator | runtime/results APIs, poller | Polls already-running jobs only | GitHub Actions or remote AI gateway | Network-free lifecycle tests | No unattended end-to-end external production proof | P1 |
| VideoAsset | CODE + TEST VERIFIED | YouTube external reference or runtime result URL/path | `assets/manager.py`, runtime worker, content sync | asset APIs, publish preflight | Created by content sync/runtime completion | YouTube/GitHub/AI result | Publish preflight and runtime contract tests | Asset readiness depends on provider result; no durable artifact replication contract | P1 |
| Publish | PARTIAL | Official YouTube API adapter exists; most tests use doubles | `publish/manager.py`, queue/worker, YouTube adapter | Publish APIs/UI, status fields | Explicit run endpoint/queue; no account scheduler | YouTube OAuth upload scope | Readiness + simulated publish tests; no real upload E2E | Human must prepare/trigger and verify real publish; status reconciliation is incomplete | P0 |
| Traffic | PARTIAL | YouTube views/engagement Analytics only | Analytics collector | Query V2/Data Center funnel traffic | Scheduled analytics reads | YouTube Analytics | Real Analytics E2E | No site/session attribution showing where traffic went | P0 |
| Intent | CODE + TEST VERIFIED | Trusted signed server/relay request; public source not configured | `/attribution/intent` → `data.growth.record_intent` | `/data/intent`, funnel/query/UI | Local contract only; no public collector | Runtime HMAC secret; optional external relay | r32 local contract PASS; public E2E not available | No public deployment/real landing collector yet | P0 |
| Conversion | CODE + TEST VERIFIED | Provider-neutral signed ingestion contract; no real provider source | `/attribution/conversion/{provider}` → `data.growth.record_conversion` | `/data/conversion`, funnel/query/UI | Adapter boundary only | Runtime HMAC; provider callback required | r32 synthetic provider PASS | Binance source not configured/discovered | P0 |
| Feedback | CODE + TEST VERIFIED | Analytics plus canonical signed/local intent/conversion rows | `feedback_bridge.refresh_account_feedback` | feedback snapshots/API/UI | Explicit refresh; deduped snapshots | None for local rules | Synthetic analytics/attribution bridge E2E | Public events and provider conversions still unavailable | P0 |
| Next Strategy | CODE + TEST VERIFIED | Feedback snapshot fields and deterministic rules | `strategy.py`, `task_generator.py` | Snapshot/UI and explicit materialize API | Recommendation generated on refresh; task creation manual | Optional provider selection | Synthetic strategy/materialization tests | No automatic Conversion → Intelligence → next ProductionTask loop | P0 |

## Verified Loop and Breaks

当前真实可达链路：

`Content Data → Analytics → Query V2/Data Center → analytics-backed Intelligence feedback → strategy recommendation → (manual) ProductionTask → (manual/explicit) Production Runtime → VideoAsset → (manual/explicit) Publish`

FIRST BROKEN LINK: **Public Traffic → Trusted Intent**。本地 signed ingestion contract 已建立并通过 r32，但公网 relay/landing collector 尚未部署，因此尚不能证明真实站外 click 到达 OS。

SECONDARY GAPS:

- Intent → Binance conversion 没有外部验证来源或 callback。
- AI feedback 当前可消费 analytics 与本地 funnel fixtures，但没有持续真实业务输入。
- Intelligence 只生成 recommendation；AI Intelligence → automatic ProductionTask creation 缺失。
- Publish 具备官方 adapter/readiness 与显式执行边界，但未完成真实无人值守发布 E2E。
- Runtime poller 只处理已提交 job，不是完整 autonomous loop。

## Autonomous Loop Node Status

| Node | Status | Evidence |
|---|---|---|
| observe content | AUTOMATIC | scheduler/content sync |
| observe analytics | AUTOMATIC | scheduled daily + backfill |
| analyze | MANUAL | explicit feedback refresh; optional remote gateway request |
| decide strategy | MANUAL | refresh returns deterministic recommendation |
| create ProductionTask | MANUAL | explicit materialize endpoint |
| produce | MANUAL | explicit task/runtime execution boundary |
| publish | MANUAL | explicit publish run; no scheduler auto-publish |
| observe platform traffic | AUTOMATIC | Analytics sync |
| observe site intent | PARTIAL | local HMAC boundary exists; public collector missing |
| observe conversion | MISSING | no external attribution source |
| learn / feedback | PARTIAL | analytics/local funnel snapshot only |
| create next task | MISSING | no automatic AI → task transition |

## Priority Gaps

### P0

1. 部署可信、去重且可关联 `content_id / session_id / source` 的站外 Intent Collector（至少覆盖 landing/CTA/referral click），连接本阶段 signed boundary。
2. 建立 Binance referral conversion 的外部回传或可验证 attribution，并连接 intent、content、account。
3. 在真实 Intent/Conversion 数据存在后，打通 feedback → strategy → **受控** ProductionTask 创建边界，并保留人工审批/执行安全门。
4. 完成真实 Publish 状态回写与上线后关联，使内容闭环能从 VideoAsset 到 platform_video_id 再回到 observation。

### P1

- Provider content/status reconciliation 与更完整历史保留。
- Production Runtime 的真实外部 provider E2E、重试与结果关联。
- 站外 traffic attribution 与 session identity 的隐私/保留策略。
- 多 provider analytics 与 publish parity。

### P2

- Data Center/Intelligence 的体验增强、更多趋势维度与 UI 告警。
- 扩展平台适配器、报表导出与 retention 配置体验。

## Recommended Next Implementation Stage

**Stage:** Real Intent + Referral Attribution Ingestion

**Why:** 这是当前 FIRST BROKEN LINK，且是从平台 analytics 走向真实增长/转化闭环的最早必要输入；继续强化 scheduler 不会修复它。

**Input:** 已发布内容的 `content_id / platform_video_id / account_id`、站外 landing/CTA/referral 事件、稳定 session/source 标识。

**Output:** 可验证、去重的 intent events 与 Binance referral conversion records，能够被 Query V2/feedback bridge 按时间和内容关联。

**External dependency:** 站点/CTA 埋点与 Binance referral conversion callback 或等价可信 attribution source。

**Real E2E acceptance criteria:** 一条真实 content → 真实 landing/referral click → 真实 conversion callback，在 DB 中可按 content/session/source 关联；Query/Data Center/feedback 展示同一链路，重复事件不重复计数；无外部事件时明确 unavailable，不伪造零值。

**What NOT to build:** 不重做 Query Engine、Analytics storage、Scheduler；不先做自动 ProductionTask、自动 Publish 或复杂 BI dashboard。

