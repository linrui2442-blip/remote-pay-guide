# Remote Pay Guide OS Blueprint v2.3

## 1. 项目定位

Remote Pay Guide OS 是 AI 驱动的远程生产运营系统。

它不是本地视频生成工具，而是在用户电脑上运行的统一控制中心，用于连接：

- Data Feedback
- AI Intelligence
- Production Execution
- Video Asset Management
- Publish
- Analytics

形成完整生产运营闭环。

核心闭环：

```
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

---

## 2. 本地电脑角色定义

Remote Pay Guide OS 运行在用户电脑上。

电脑的职责：

- 运行 OS 控制中心
- 管理 Production Task
- 选择 Provider
- 调用 AI 服务
- 管理 Video Asset
- 控制 Publish
- 收集反馈数据

电脑不是视频推理服务器。

禁止理解为：

```
PC
↓
Local GPU
↓
Local AI Model
↓
Generate Video
```

系统不要求本地 GPU 推理。

---

## 3. Legacy Production Compatibility Layer

历史 short01-short10 生产流程必须保持兼容。

```
Production Task File
↓
GitHub Actions
↓
Render Workflow
↓
Production Script
↓
Artifact
↓
Video Asset
↓
Publish
```

GitHub Production 是已有 Production Execution Engine，不替代。

---

## 4. Production Architecture

Production Task 进入 Provider Selection。

```
AI Intelligence
        ↓
Production Task
        ↓
Provider Selection
      /        \
     /          \
GitHub Production   AI Remote Production
     |                    |
GitHub Provider      AI Gateway Provider
     |                    |
GitHub Actions       AI API Relay
     |                    |
Existing Pipeline   External AI Video Service
          \          /
           \        /
        Production Result
              ↓
        Video Asset Layer
              ↓
        Publish Center
```

---

## 5. GitHub Production

GitHub Production 负责：

- 接收 Production Task
- 执行 GitHub Actions
- 调用已有生产流程
- 输出 Production Result

它不是：

- 内容决策系统
- AI 策略系统

---

## 6. AI Remote Production

AI Production 不是本地模型生产。

正确流程：

```
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

AI Provider 必须保持抽象，不绑定单一 AI 模型。

---

## 7. Video Asset Center

Video Asset Center 是统一资产抽象层。

负责：

- Asset Registry
- Asset URL
- 来源记录
- 状态管理
- 生命周期管理

文件来源可以包括：

- GitHub Artifact
- External Asset URL
- AI Provider Output

---

## 8. Publish Center

Publish Center 负责：

```
Video Asset
↓
Publish Task
↓
Platform Adapter
↓
Social Platforms
```

不直接绑定生产来源。

---

## 9. Data Center / Data Feedback Loop

Data Center 不是单纯的视频统计库，也不只是保存 Production / Publish 状态。

它是 Remote Pay Guide OS 的统一增长数据中枢，必须把内容生命周期与流量、用户意图、商业转化连接起来。

核心数据链路：

```
Content
↓
Production Result
↓
Video Asset
↓
Publish Data
↓
Traffic
↓
User Intent
↓
Conversion
↓
AI Intelligence
```

Data Center 收集和关联：

- Content Registry / content_id
- Production Result
- Video Asset
- Publish Data
- Platform Traffic Metrics
  - impressions
  - views
  - clicks / CTR
  - watch time
  - average view duration
  - retention
  - likes / comments / shares
- Landing Page / GA4 User Intent Events
  - page_view
  - payment_type_select
  - payer_type_select
  - exchange_status_select
  - new_to_exchange_identified
  - binance_referral_click
- Conversion Data
  - referral conversion
  - signup / attributed conversion when available
  - conversion value when available
- Execution Performance

Remote Pay Guide 的业务漏斗必须保持：

```
Content
↓
Traffic
↓
User Intent
↓
Binance Referral Conversion
```

AI Intelligence 的判断目标不是只优化播放量，而是判断：

```
哪类内容
↓
带来哪类流量
↓
产生什么用户意图
↓
最终带来什么转化
```

### Data Center 存储边界

- `content-registry/registry.json` 与 `database/content.db` 属于已有 Content Registry / 历史迁移资产，继续保留并兼容，不应被重复开发或破坏。
- OS 运行时模块使用 `os/database/os.db` 保存 Production、Asset、Publish、Analytics、Event 以及增长反馈运行状态。
- 新能力优先扩展现有 `os/backend/data/` 和 `os/backend/analytics/`，不要再创建第二套 Data Center。

---

## 10. 开发原则

保持：

- Legacy GitHub Production 兼容
- 双生产架构
- Provider 解耦
- Data Feedback Loop
- Content → Traffic → Intent → Conversion 业务漏斗
- 本地控制中心

禁止：

- 破坏现有 Production Pipeline
- 将系统设计为本地 AI 推理工作站
- 绑定单一 AI 模型
- 将 Asset Center 等同文件存储
- 重复创建 Data Center、Analytics 或 Tracking 系统
- 用只看播放量的模型替代完整增长反馈链路

术语统一：

使用：

- AI Remote Production Line
- AI Gateway Production Line

避免使用会误导为本地模型推理的“Local AI Production Line”。
