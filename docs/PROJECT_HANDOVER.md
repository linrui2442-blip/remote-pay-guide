# Remote Pay Guide OS — 完整项目交接文档

> 交接时间：2026-09-07
>
> 交接目标：让新的 ChatGPT / 开发窗口能够直接从当前断点继续开发，不漂移、不重新设计、不重复开发已有能力。
>
> 当前仓库：`linrui2442-blip/remote-pay-guide`
>
> 默认分支：`main`
>
> 本文最近一次仓库对齐审计基线：`4f8a85f4b55b121fbc3f282bcd28ecb85988008b`
>
> 基线提交说明：`docs: clarify source code and runtime architecture boundary`

---

# 0. 新窗口接管时必须先遵守的规则

新窗口不要先给方案，不要重新规划整个系统，也不要先问用户“接下来想做什么”。

接管顺序必须是：

```text
1. 读取本文件
2. 读取 docs/REMOTE_PAY_GUIDE_OS_BLUEPRINT.md
3. 检查 GitHub main 当前 HEAD
4. 直接读取当前代码验证本文断点
5. 从“当前开发断点 / 后续开发顺序”继续执行
```

## 唯一事实优先级

发生冲突时按以下优先级判断：

```text
当前 main 分支真实代码
    > 本交接文档
    > docs/REMOTE_PAY_GUIDE_OS_BLUEPRINT.md
    > 其他历史 docs
    > 旧聊天中的计划/猜测
```

尤其注意：

- `docs/PROJECT_STATUS.md` 中仍有很多早期 Phase 11–14 的历史状态，不能把它当成当前 OS 开发断点。
- `docs/PROJECT_HANDOVER.md` 旧版本只覆盖 short04/short05 Legacy Video Factory，现已由本文完整替换。
- 不允许根据旧文档重新搭第二套 Production / Data Center / Analytics / Publish / OAuth。
- 仓库代码存在就扩展；不存在才新增。

## 用户工作方式

用户明确要求：

- 进入执行模式。
- 不要频繁询问确认。
- 能直接检查代码、修复、提交、跑 CI 的工作就直接做。
- 只有遇到真正需要用户本机、第三方授权、凭据、真实外部发布等阻断时再停下来。
- 不要只回复“下一步建议”，要实际推进代码。

---

# 1. 项目定位：不要漂移

Remote Pay Guide OS 不是单一视频生成工具，也不是 YouTube 客户端。

它是一个 **AI 驱动的内容生产与增长运营控制系统**，运行在用户电脑上，统一连接：

```text
Data Feedback
↓
AI Intelligence
↓
Production Task
↓
Production Execution
↓
Video Asset
↓
Publish
↓
Traffic / Intent / Conversion
↓
Data Feedback
```

业务闭环必须保持：

```text
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

AI Intelligence 的目标不是单纯追播放量，而是判断：

```text
什么内容
→ 带来什么流量
→ 产生什么用户意图
→ 最终带来什么转化
```

---

# 2. 绝对不能改错的架构边界

## 2.1 双生产线必须保留

### A. GitHub Production Line

这是已有生产线，负责 Legacy / GitHub Actions 生产。

```text
Production Task
↓
GitHub Provider
↓
GitHub Actions
↓
Existing Render Pipeline
↓
Production Result
↓
Video Asset
```

历史 `short01-short10` 必须继续兼容。

### B. AI Remote / AI Gateway Production Line

正确设计：

```text
Production Task
↓
AI Gateway Provider
↓
AI API Relay / Gateway
↓
External AI Video Generation Service
↓
Video Result
↓
Production Result
```

严禁重新设计成：

```text
PC
↓
Local GPU
↓
Local AI Model
↓
Generate Video
```

用户电脑是控制中心，不是本地 AI 视频推理服务器。

统一术语：

- `AI Remote Production Line`
- `AI Gateway Production Line`

避免使用会误导的 `Local AI Production Line`。

---

# 3. Legacy 生产线：必须保护，禁止重做

以下已有生产链继续保留：

```text
JSONL Content Task
↓
.github/workflows/render-launch02.yml
↓
render_batch.py
↓
MoneyPrinterTurbo
↓
polish_short.py
↓
GitHub Artifact
↓
GitHub Pages media URL
↓
Legacy Publish / Postiz compatibility
```

历史验证资产/流程包括 short01-short10。

重要规则：

- 不要重写 `render-launch02.yml`。
- 不要重写 MoneyPrinterTurbo 集成。
- 不要重写历史 JSONL 任务体系。
- 不要为了 OS 新架构破坏 Legacy pipeline。
- Legacy Postiz 保留历史兼容，但 **正式 OS Publish Center 不依赖 Postiz**。

---

# 4. 当前 OS 后端总入口

后端入口：

`os/backend/main.py`

当前 FastAPI 已注册的主要路由域：

- production
- runtime
- results
- data
- ai
- intelligence
- publish
- analytics
- assets
- oauth
- accounts
- settings

应用 lifespan 会启动 Production runtime poller。

这意味着当前系统已经不是“静态 Dashboard”，而是有真实运行时的 OS 控制中心。

---

# 5. 当前本地运行方式

从当前 repo root 启动。仓库目录名不是架构要求；本次审计时本地目录名为 `remote-pay-guide-git`。

```text
<repo-root>
```

后端：

```powershell
cd <repo-root>
python -m uvicorn main:app --app-dir os/backend --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd <repo-root>\os\frontend
npm.cmd run dev
```

PowerShell 可能因为执行策略阻止 `npm.ps1`，所以优先使用 `npm.cmd`。

前端默认：

```text
http://localhost:5173
```

后端默认：

```text
http://127.0.0.1:8000
```

注意：如果本地代码刚同步了后端路由，必须重启后端；Vite 前端通常只需刷新。

---

# 6. 网络代理：已开发，不要重复做

之前浏览器可以通过 Clash Verge 访问 Google，但 Python 后端直连会超时，因此已经完成 OS 显式代理配置。

当前实现：

- `os/backend/config/network.py`
- `os/backend/integrations/google_transport.py`
- Settings 路由
- 前端“系统设置 → 代理配置”

支持模式：

- manual
- system
- disabled

用户此前确认 Clash Verge System Proxy 使用端口：

```text
7897
```

曾配置为：

```text
http://127.0.0.1:7897
```

新窗口不要把这个端口硬编码进代码。它是运行时设置，用户以后可在 UI 改。

Google / YouTube API 相关后端调用应复用现有代理 transport，不要另造 requests session 绕开配置。

---

# 7. Platform Registry：已经完成，禁止再硬编码平台核心逻辑

当前 Publish Registry：

`os/backend/publish/registry.py`

已支持动态 Adapter 发现。

新增平台的正确方式：

```text
新增 Adapter module
↓
Registry 自动发现 / 注册
↓
声明 Capability
↓
接入对应账号连接 / 内容同步 / Analytics / Publish runtime
```

不要为了新增 X / LinkedIn / Reddit / Pinterest / Threads 等平台去修改 Data Center 核心模型或写新的平台核心分支。

当前已知平台：

- YouTube
- Facebook
- Instagram
- TikTok

但是要区分“Adapter 已注册”和“真实发布能力已完成”。

当前真实状态：

- YouTube：`live_api`，可进入正式 OS 发布链。
- Facebook：当前只是 placeholder/simulated Adapter，不能当成真实 OS live publish。
- Instagram：当前只是 placeholder/simulated Adapter。
- TikTok：当前只是 placeholder/simulated Adapter。

UI 和后端已经开始使用 `publish_ready` / `execution_mode` 来避免把 placeholder 误标成真实可发布。

不要重新把 `status=ready` 简单等价为“真实平台发布已打通”。

---

# 8. Platform Account / OAuth：YouTube 已打通，不要重做

账号域：

- `os/backend/accounts/`
- `os/backend/routers/accounts.py`

OAuth 域：

- `os/backend/oauth/`
- `os/backend/routers/oauth.py`

前端 OAuth callback：

```text
/oauth/youtube/callback
```

实际前端组件为 provider-neutral callback 架构，不应重新退回 YouTube-only 页面逻辑。

## YouTube OAuth 已完成的关键修复

已经处理：

- PKCE
- state 单次消费
- `code_verifier` 跨 redirect 保存
- Google scope superset 行为
- token 刷新
- google-auth expiry 时区兼容
- read / analytics / upload scopes
- frontend callback

用户已经真实完成过 YouTube 授权，看到：

```text
授权完成 — YouTube 已连接，发布与 Analytics 权限已经写入本地 OS。
```

不要重新设计 OAuth，不要创建第二套 token 表，也不要因为新平台再复制一整套 YouTube OAuth 栈。

---

# 9. YouTube 内容同步：已完成，不要重复开发

用户已经真实执行过 YouTube 内容同步：

```text
同步完成：发现 10 个视频，新导入 10 个，已存在 0 个。
```

同步逻辑：

- 通过 YouTube Data API
- 保存远程 metadata/reference
- 不下载视频文件到用户电脑
- 已存在视频按 `platform_video_id` 幂等处理
- 创建/关联已发布 PublishTask

远程 YouTube 视频的 VideoAsset 是 metadata/reference，不是可再次上传的本地源文件。

因此 Publish Center 前端已经专门排除：

```text
metadata.synced_from === "youtube"
```

这类远程同步资产不能进入“重新发布资产选择器”。

不要删除这个保护，否则会出现“把已经同步来的 YouTube 视频又当成源文件上传”的错误行为。

---

# 10. 评论同步：明确禁止重新引入

用户明确要求过：

```text
不要做评论同步，撤销删除仓库中关于评论同步的修改
```

评论文本同步已经完整回滚。

最终回滚基线验证：

```text
a446605ff900c0aefcb10d73ba0e18b66df8b74d
```

不要重新引入：

- commentThreads
- 评论正文
- 评论样本
- audience comment feedback pipeline

注意：YouTube Analytics 中 `comments` 作为**数值聚合指标**可以保留，这不等于评论内容同步。

---

# 11. Analytics / Data Center：主体能力已存在，不要造第二套

Data Center 是统一增长数据中枢，不是单纯播放量表。

OS 运行时主数据库：

```text
os/database/os.db
```

历史 Content Registry / Migration 资产：

```text
content-registry/registry.json
database/content.db
```

这两套历史资产需要兼容，但不要复制一套新的 Data Center。

## Analytics 已有能力

YouTube Analytics 已接入官方 API v2，当前核心指标包括：

- views
- watch_time
- average_view_duration
- retention
- likes
- comments（仅聚合数值）
- shares

账号级批量 Analytics 同步已经完成。

关键实现：

- `os/backend/analytics/youtube_api.py`
- `os/backend/analytics/collector.py`
- `os/backend/analytics/manager.py`
- `os/backend/analytics/publish_bridge.py`
- `os/backend/routers/analytics.py`

已有 API 包括：

```text
POST /analytics/collector/collect
POST /analytics/collector/collect/publish-task/{task_id}
POST /analytics/collector/collect/account/{account_id}
GET  /analytics/metrics/current
```

账号级批处理原则：

- 只处理 eligible/published PublishTask
- 一个视频失败不阻断整批
- 成功和失败分别返回
- 不伪造 0 数据替代真实失败

## 账号级一键同步

平台账号页已有“同步全部”逻辑，统一走：

```text
Content Sync
↓
Analytics Sync
↓
AI Intelligence Feedback
```

关键路由：

```text
POST /accounts/{account_id}/sync-all
```

不要重新新增“第二个全量同步入口”。

---

# 12. Data Feedback / Growth / Conversion：已经有基础，不要只看播放量

Data Center 已经存在增长数据模型，用于关联：

```text
Content
→ Publish
→ Traffic
→ Intent
→ Referral Click
→ Conversion
```

GA4 业务事件设计包括：

- page_view
- payment_type_select
- payer_type_select
- exchange_status_select
- new_to_exchange_identified
- binance_referral_click

增长反馈和 AI Intelligence 需要继续围绕“转化优先”工作。

现有策略方向已经是：

```text
conversion > referral intent > intent > traffic vanity metric
```

不要重新实现“只按 views 排名然后自动生成内容”的简化版本。

---

# 13. AI Intelligence：已有反馈/策略/任务物化能力

现有目录：

```text
os/backend/intelligence/
```

已有能力包括：

- feedback
- strategy
- task_generator
- 从 Data Center 增长结果生成下一步策略
- 将策略物化为下一轮 Production Task

前端 Data Center 已有 Intelligence 控件，并明确提示：

```text
创建下一轮生产任务
不会自动运行或发布
```

这是重要安全边界：

```text
AI Intelligence 可以生成下一轮任务
≠ 自动执行生产
≠ 自动发布
```

不要改成无人确认的全自动外部发布链。

---

# 14. Production Center：已经是运行时系统，不要再造 Scheduler

Production 已经具备：

```text
Production Task
↓
Scheduler
↓
Runtime Job
↓
Provider
↓
Result
↓
Video Asset
```

已有后台 poller，会随 FastAPI lifespan 启动。

GitHub Provider 已经真实打通过：

```text
ProductionTask
→ GitHub Actions
→ Run Discovery
→ Completion Tracking
→ Artifact
→ GitHub Pages
→ public asset URL
→ Video Asset
```

AI Gateway provider 设计已经存在，并且前端“系统设置”已有远程 endpoint 配置。

重要：

- AI Gateway 只能连接远程 HTTP / 外部 AI 服务。
- 不允许回退到本地 GPU / 本地模型。
- 如果 endpoint 未配置，UI 应显示未就绪，而不是偷偷换本地执行。

---

# 15. Video Asset Center：已存在，不要重新做文件库

核心：

```text
os/backend/assets/
```

Video Asset 是统一抽象，不等于 mp4 文件本身。

来源可以是：

- GitHub Production
- GitHub Pages public asset
- external URL
- AI Gateway output
- synced remote metadata/reference

关键字段包括：

- asset_id
- video_id
- production_result_id
- source_provider
- storage_type
- asset_url
- file_path
- status
- metadata
- source
- location

Publish Center 只应选择真正可解析、可作为源上传的 ready asset。

---

# 16. Publish Center：当前开发重点，已经完成大部分核心链

这是本次交接最重要的当前断点。

## 16.1 正式 OS Publish Chain

目标架构：

```text
Video Asset
↓
Publish Task
↓
Publish Contract Validation
↓
Platform Adapter
↓
Official Platform API
↓
platform_video_id / published_url
↓
Analytics
```

OS 正式发布路径不调用 Postiz。

## 16.2 当前关键文件

后端：

- `os/backend/publish/models.py`
- `os/backend/publish/manager.py`
- `os/backend/publish/orchestrator.py`
- `os/backend/publish/worker.py`
- `os/backend/publish/queue.py`
- `os/backend/publish/registry.py`
- `os/backend/publish/asset_resolver.py`
- `os/backend/publish/adapters/youtube.py`
- `os/backend/publish/adapters/youtube_api.py`
- `os/backend/routers/publish.py`

前端：

- `os/frontend/src/pages/PublishCenter.jsx`
- `os/frontend/src/api.js`
- `os/frontend/src/App.jsx`

## 16.3 已完成的发布安全契约

当前已经实现：

### 创建任务 != 发布

```text
POST /publish/tasks
```

只做：

- platform 校验
- account 校验
- asset 校验
- adapter readiness 校验
- OAuth/account preflight
- 幂等重复任务检查
- 持久化 pending PublishTask

不会自动上传。

### 显式执行发布

```text
POST /publish/tasks/{task_id}/run
```

只有用户点击“立即发布”/明确调用时才进入 worker。

### 幂等保护

相同：

```text
asset + platform + account
```

如果已经有 active pending/publishing/published 任务，不重复创建。

### 状态保护

只有：

```text
pending
failed
```

允许显式执行。

已 published 的任务不能重复执行。

### 未来 scheduled_time 保护

如果 scheduled_time 还没到，显式 run 会拒绝。

### placeholder 平台保护

Facebook / Instagram / TikTok 当前不会被当成真实 live publish。

### YouTube OAuth preflight

最新一段开发已经加入：

```text
account exists
+ platform == youtube
+ OAuth credential exists
+ token material usable
+ youtube.upload scope granted
```

不满足时，PublishTask 创建阶段就直接阻断，不等到上传时才失败。

## 16.4 当前 readiness API

```text
GET /publish/readiness/{platform}
GET /publish/readiness/{platform}?account_id=<id>
```

会返回：

- adapter_registered
- publish_ready
- execution_mode
- reason
- account_readiness
- overall ready

这是后续 UI / 新平台应复用的统一 preflight 接口，不要为每个平台再造一套 readiness API。

---

# 17. YouTube Publish Adapter：代码已是真实 API 路径，但真实上传仍需单独验证

YouTube Adapter 当前声明：

```text
execution_mode = live_api
publish_ready = initialized/ready
```

上传链会：

```text
account_id
↓
OAuth token
↓
ensure_valid_token
↓
Google credentials
↓
YouTubeAPIClient
↓
upload_video
```

Publish Worker 会先通过 AssetResolver 将 URL/Asset 解析成上传所需临时文件，然后调用 YouTube adapter。

当前必须区分：

```text
代码链已接通 / CI 契约已通过
≠ 已经执行过本轮真实 YouTube 上传验证
```

本次交接时，不要把“真实 YouTube 发布已最终验证”写成完成。

除非用户明确要求，不要擅自做真实视频上传。

---

# 18. Publish Center 前端：已经接入 App

`App.jsx` 当前已使用：

```text
<PublishCenter />
```

而不是旧的只读发布任务表。

Publish Center UI 当前已经包含：

- 平台实时发布 readiness
- 只显示 live publish 平台作为新任务平台选项
- 账号选择
- Ready Video Asset 选择
- title
- description
- tags
- privacy status
- 创建发布任务
- pending/failed 任务“立即发布 / 重试发布”
- published 任务 Analytics 采集

前端已经明确提示：

```text
创建任务不会自动上传
只有点击“立即发布”才执行外部发布
```

并且远程同步来的 YouTube 视频不会出现在可重新发布资产列表。

---

# 19. Publish Center 历史关键提交

本次 Publish Center 收口相关提交顺序（从较早到当前）包括：

```text
74128235e8f1393e9c34b3a956b83c8b4ed292ac
Add guarded Publish Center prepare and run routes

80fd7242ce1ef4dd79d27b896ee3711f09c790db
Add Publish Center execution contract smoke test

0a8daf049dec9c811bd5c212881dd643447b8c07
Verify guarded Publish Center execution contract

6fe0bfdde8d613bf78c041956911ada2cfbbcb38
Add Publish Center prepare and run frontend API

9d32f9057c51d8b7bf5bfe4803403de90eb6d4e4
Add guarded Publish Center UI

b709e700bd8a48a20d5211fac8d474cdc6a210fc
Wire guarded Publish Center UI into OS

e4c257456022ad6d80263d75eb73e36b1a6c39a7
Show truthful live publish readiness in OS UI

21708beed1e35513674b6318e0cf7df6d4f83c83
Exclude synced remote videos from publish asset picker

235392edaba37438d444171c9ec3c15476335b68
Guard YouTube publishing with account OAuth readiness

ee2df6d39161e4b2cfc0c64403867fa555e85d99
Add account-level publish credential preflight

7f7b63255ec3a3e70d24433a39bd703dedbae279
Expose account publish preflight readiness

418cd098148dbd8a9ac44a1e1bbe4a80cc79a560
Verify account OAuth preflight before YouTube publish task creation
```

上述 Publish Center 收口阶段的基线 HEAD 为：

```text
418cd098148dbd8a9ac44a1e1bbe4a80cc79a560
```

本次仓库对齐审计的 main 基线已前进到：

```text
4f8a85f4b55b121fbc3f282bcd28ecb85988008b
```

---

# 20. 已记录的历史 CI 状态

Publish Center 收口阶段曾确认：

```text
OS YouTube Publish Readiness
Run ID: 34073784262
HEAD: 418cd098148dbd8a9ac44a1e1bbe4a80cc79a560
Conclusion: success
```

这说明该历史 HEAD 的 account OAuth preflight / Publish readiness 契约在 CI 中通过；
不要把它误读为当前 main 的实时 Actions 结论。

此前 Publish Center 前端接入后，OS Frontend Verification 也已经通过构建和前端约束检查。

新窗口如果继续改 Publish Center / OAuth / frontend，必须继续看对应 CI，不允许提交后不验证。

---

# 21. 已完成能力清单：不要重复开发

下面这些能力都已经存在。新窗口只能修 bug / 扩展，不要重新创建第二套。

| 能力 | 当前已有位置/状态 | 禁止重复动作 |
|---|---|---|
| Canonical Production Task | `os/backend/production/` | 不要再建另一套 ProductionTask |
| Production Scheduler/Runtime | `production/tasks`, `production/runtime` | 不要再造新 scheduler/runtime |
| Runtime Poller | FastAPI lifespan 启动 | 不要写第二个后台轮询器 |
| GitHub Provider | 已打通 GitHub Actions | 不要替换 Legacy GitHub Production |
| AI Gateway Provider | 已有远程 provider/settings | 不要改成本地模型 |
| Video Asset Registry | `os/backend/assets/` | 不要另建 asset DB |
| Publish Manager | `os/backend/publish/manager.py` | 不要另建 publish_tasks 系统 |
| Publish Registry | `publish/registry.py` | 不要硬编码核心平台列表 |
| Publish Orchestrator | `publish/orchestrator.py` | 不要再建“另一个发布服务层” |
| YouTube Official Publish Adapter | `publish/adapters/youtube*.py` | 不要退回 Postiz 做正式 OS 发布 |
| Accounts | `os/backend/accounts/` | 不要复制账号表 |
| OAuth | `os/backend/oauth/` | 不要复制 token/state 系统 |
| Proxy | `config/network.py` + Google transport | 不要硬编码 7897 |
| YouTube Content Sync | integrations sync | 不要重新开发 10 视频导入 |
| Sync Planner/Scheduler | integrations sync planner/scheduler | 不要再建第二个 sync-all |
| Analytics Storage | `analytics/manager.py` | 不要再建 metrics 数据库 |
| YouTube Analytics | `analytics/youtube_api.py` | 不要用假数据代替 API |
| Account Analytics Batch | `analytics/publish_bridge.py` | 不要重做账号级批采集 |
| Data Center | `os/backend/data/` + frontend DataCenter | 不要创建第二套 Data Center |
| Growth/Intent/Conversion | data/growth 等 | 不要只做 views 统计 |
| AI Intelligence | `os/backend/intelligence/` | 不要再造独立策略系统 |
| Platform Capability Registry | `data/platform_capabilities.py` | 不要为每个平台加核心列 |
| Frontend Control Center | React/Vite | 不要迁移新框架 |
| Publish Center UI | `pages/PublishCenter.jsx` | 不要恢复旧只读发布页 |

---

# 22. 明确还没有完成 / 不要误判 PASS 的部分

## 22.1 本轮真实 YouTube 上传尚未最终验证

代码已经具备：

- live YouTube Adapter
- OAuth token
- upload scope preflight
- AssetResolver
- explicit run
- result/status 持久化

但本文交接时 **没有把“真实上传一条新 private 视频并确认平台返回”作为已完成事实**。

真正 PASS 需要至少确认：

```text
PublishTask pending
↓
explicit run
↓
YouTube API upload success
↓
platform_video_id 非空
↓
published_url 非空
↓
status = published
```

真实外部上传必须等用户明确要求后执行。

## 22.2 Facebook / Instagram / TikTok 正式 OS live publish 未完成

现阶段只保留 Adapter/Registry 位置，不应在 UI 宣称 live ready。

## 22.3 AI Gateway 外部真实视频服务是否可运行取决于远程 endpoint 配置

代码架构已存在，但不要假设用户当前一定已经配置了可用 provider endpoint。

## 22.4 GA4 / Referral Conversion 的真实流量闭环仍需要持续真实数据验证

不能因为 schema/API 已有，就宣称业务转化闭环已经获得足够生产数据验证。

---

# 23. 当前开发断点：新窗口从这里接

## 当前断点定义

```text
Data Center Query V1 已存在并由前端实际使用。
它支持 account/platform/scope/metrics/sorting，以及 referral、conversion、conversion value。
Query V2 尚未实现 date range、time series、previous-period comparison、interval/group_by。
下一步不应重构 Publish；应先定义安全的时序指标语义，再扩展 Query V2。
```

当前断点精确位于 `os/backend/data/query.py::query_data_center`、
`os/backend/routers/data.py::data_query` 与 `os/frontend/src/pages/DataCenter.jsx::loadQuery`。
YouTube Analytics 当前采集的是默认 28 个完整日或调用方指定窗口的窗口聚合；不能直接
`SUM(snapshot.views)` 构造时间序列，否则重叠窗口会重复计数。

---

# 24. 后续开发顺序：严格按此顺序，避免漂移

## P0 — Data Center Query V2 的时序契约与最小实现

先固定统一 metric contract 和窗口语义，再为 `/data/query` 增加 `start_date`、`end_date`、
`interval/group_by`、time-series 和 previous-period comparison。验收必须证明重叠的 28 日窗口
不会被相加重复计数，并覆盖 account/platform/scope/growth 指标组合。

不要新增第二个 Query Engine，也不要添加 `youtube_views` 一类平台专属核心列。

## P1 — 验证 Publish Center 本地非破坏性 preflight

打开：

```text
发布中心
```

验证：

- YouTube 显示 live publish readiness
- Facebook / Instagram / TikTok 不显示为 live
- 已连接 YouTube 账号能被选择
- 没有 OAuth/upload scope 时应在任务创建前阻断
- synced-from-YouTube 的远程资产不出现在上传 asset picker
- 真正 ready、可解析的生产资产能被选择
- 点击“创建发布任务”只创建 pending，不上传
- 重复创建同资产/平台/账号不会新增重复任务

如果此处报错，直接根据错误定位代码修复，不要重新设计架构。

## P2 — 用户明确允许后，做一次 YouTube Private 真发布验证

只有用户明确说可以真实上传时再执行。

建议只验证一条：

```text
Ready Video Asset
→ YouTube connected account
→ privacy = private
→ 创建 PublishTask
→ 显式立即发布
```

验收必须看：

- status
- platform_video_id
- published_url
- error_message
- YouTube 后台真实存在 private 视频

失败就修最小故障点，不要回退 Postiz，不要重构整个 Publish Center。

## P3 — 发布成功后闭合 Data Feedback

真实发布成功后：

```text
Publish result
↓
Analytics collection
↓
Data Center current metrics
↓
AI Intelligence feedback
↓
Next Production Task materialization
```

这里重点是确认已有各层真实连通，不是重复实现各层。

## P4 — YouTube 单平台闭环稳定后，再扩其他平台

新增平台顺序必须遵守：

```text
Adapter
→ Account Connector/OAuth
→ Live Publish Readiness
→ Content Sync（如支持）
→ Analytics Collector（如支持）
→ Registry capability
```

不要修改核心 Data Center / Publish Center 来迎合某个平台。

## P5 — 再推进真实 AI Gateway 外部生成

在 Publish 单平台闭环稳定后，再接具体外部 AI Video Provider。

必须保持：

```text
OS
→ AI Gateway
→ External AI Service
```

不得回退本地 GPU。

---

# 25. 新窗口排障原则

发生错误时按以下层级查：

```text
1. 当前 main 代码是否已同步到本地
2. backend 是否重启
3. frontend 是否刷新 / Vite 是否读取新代码
4. OS proxy 是否可用
5. account 是否连接正确平台
6. OAuth token 是否存在
7. scope 是否包含所需能力
8. asset 是否真正 ready / 可解析
9. platform adapter 是否 publish_ready
10. external API 返回什么真实错误
```

不要第一时间：

- 重写 OAuth
- 换 Postiz
- 重写 Scheduler
- 新建数据库
- 新建 Data Center
- 新建 Analytics 系统
- 新建 Platform Registry
- 重新实现 YouTube Content Sync

---

# 26. GitHub 操作规则

用户允许直接推进 main 开发。

新窗口应：

- 已知路径优先直接 `fetch_file`。
- GitHub code search 没结果不代表文件不存在。
- 修改前读取当前 blob SHA。
- 每次实际修改后记录 commit SHA。
- 对应 workflow 要看真实 Actions 结论。
- 不要声称“已经修改”但实际上没有写入仓库。

Actions 检查可按 head SHA 查询。

---

# 27. 真实外部操作边界

以下操作不要擅自执行：

- 新 OAuth 授权
- 真实 YouTube 视频上传
- Facebook / Instagram / TikTok 真实发帖
- 真实 AI Gateway 付费生成
- 删除远程内容

除非用户明确要求。

但以下操作无需反复问：

- 读代码
- 写代码
- 修 bug
- 提交 GitHub
- 添加/修 CI smoke test
- 检查 Actions
- 更新文档
- 非网络 smoke test

---

# 28. 用户明确不想要的行为

不要：

- 每一步都问“要不要继续”。
- 把已经完成的模块重新列为新计划开发。
- 因为看见旧 docs 就回滚到旧 Phase。
- 把 Remote Pay Guide OS 说成“本地 AI 视频生成器”。
- 重新引入评论同步。
- 把 placeholder adapter 说成真实平台发布已完成。
- 把 YouTube 同步的视频下载/备份到 PC。
- 为了新平台给 Data Center 加 `youtube_views` / `tiktok_views` 这类平台专属核心列。
- 用 Postiz 替代正式 OS YouTube API 发布。

---

# 29. 新窗口第一条执行指令（可直接复制）

```text
你现在接管 Remote Pay Guide OS 的持续开发。

仓库：linrui2442-blip/remote-pay-guide
分支：main

先读取并严格遵守：
1. docs/PROJECT_HANDOVER.md
2. docs/REMOTE_PAY_GUIDE_OS_BLUEPRINT.md

当前交接审计基线 HEAD 是：
4f8a85f4b55b121fbc3f282bcd28ecb85988008b

如果 main 已经前进，以当前 main 代码为最高事实来源，但必须保持交接文档里的架构边界和禁止项。

不要重新规划系统，不要重复开发已有 Production / Asset / Publish / OAuth / Analytics / Data Center / Intelligence / Platform Registry。
不要重新引入评论同步。
不要把 AI Gateway 改成本地 GPU 推理。
不要让正式 OS Publish 回退 Postiz。

当前断点是：Data Center Query V1 已存在并由前端使用；Query V2 的 date range、time series、period comparison、interval/group_by 尚未实现。先解决窗口聚合 snapshot 的时序语义，禁止直接 SUM 重叠窗口。Publish 的真实 YouTube private upload 仍需用户明确授权后验证。

进入执行模式：先检查当前 main 与用户本地是否同步，然后从 docs/PROJECT_HANDOVER.md 的 P0 → P1 顺序继续。能直接检查/修复/提交/跑 CI 的事情就直接做，不要频繁问我。只有涉及真实 OAuth、真实上传、外部付费生成等用户动作时再停下来。
```

---

# 30. 交接结论

当前 Remote Pay Guide OS 已经具备：

```text
Production Runtime
+ GitHub Production Bridge
+ AI Gateway Architecture
+ Video Asset Center
+ Platform Registry
+ Account/OAuth
+ YouTube Content Sync
+ YouTube Analytics
+ Data Center / Growth Feedback
+ AI Intelligence
+ Guarded Publish Center
+ YouTube Official Publish Adapter
+ Publish OAuth Preflight
```

当前最重要的工程原则不是“继续加模块”，而是：

```text
不要重复开发
不要漂移架构
先闭合已有单平台真实链路
再扩平台 / AI Provider
```

新窗口应从本文第 24 节的 P0 继续。
