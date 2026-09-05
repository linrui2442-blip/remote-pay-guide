# Remote Pay Guide OS Blueprint v2.1

## 1. 项目定位

Remote Pay Guide OS 是 AI 驱动的远程生产运营系统。

它不是本地视频工具，而是连接：

- Data Feedback
- AI Intelligence
- Production Execution
- Online Asset Management
- Publish
- Analytics

的完整生产运营闭环。

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
Analytics
↓
Data Feedback
```

---

# 2. Legacy Production Compatibility Layer

Remote Pay Guide OS 当前架构是在已有内容生产体系基础上的升级。

历史 short01-short10 生产流程必须保持兼容。

## Legacy Production Flow

真实历史流程：

```
Content Strategy

↓

Production Task File
(tasks-launch02.jsonl)

↓

GitHub Actions workflow_dispatch

↓

render-launch02.yml

↓

render_batch.py

↓

MoneyPrinterTurbo

↓

batch-output

↓

GitHub Actions Artifact

↓

GitHub Pages Media URL

↓

Postiz

↓

Social Platforms
```

说明：

历史 short01-short10 的生产由已有 Production Task 文件驱动。

当前仓库可以确认 Task 文件和执行链路，但不能证明历史 Task 文件最初来源于 AI Intelligence。

---

## workflow_dispatch 定义

workflow_dispatch 代表：

Manual Trigger

不代表：

Manual Production

需要区分：

执行触发：

谁启动 Workflow Run。

生产逻辑来源：

Production Task / Template / Parameters。

历史流程中：

人工负责：

- 启动 GitHub Workflow

生产体系负责：

- 提供 Production Task
- 提供模板
- 提供生产参数

---

# 3. Production Task Evolution

## Stage 1: Legacy

```
Content Strategy

↓

Production Task File

↓

GitHub Workflow
```

## Stage 2: Remote Pay Guide OS

```
Production Center

↓

Runtime

↓

Provider
```

## Stage 3: AI Orchestration

```
Data Center

↓

AI Intelligence

↓

Production Task Generation

↓

Provider Selection

↓

GitHub Production / AI Production
```

---

# 4. AI Intelligence

AI Intelligence 是系统智能决策层。

职责：

1. 分析 Data Center 数据
2. 生成生产策略
3. 生成 Production Task
4. 选择生产线路
5. 优化未来生产流程

AI Intelligence 不直接执行生产。

历史 short01-short10 不定义为 AI Intelligence 自动生成。

---

# 5. 双生产线路

Production Task 进入 Provider Selection。

```
                 AI Intelligence
                        |
                        ↓
                 Production Task
                        |
              Provider Selection
                  /          \
                 /            \

        GitHub Production    AI Production
                 |            |
          GitHub Provider  AI Gateway Provider
                 |            |
          GitHub Actions   AI Model/API
                 |            |
        Render Workflow  Video Result
                 \            /
                  \          /

              Production Result
                        |
                        ↓
              Video Asset Layer
                        |
                        ↓
              Publish Center
                        |
                        ↓
              Platforms
```

---

# 6. GitHub Production

GitHub Production 不是：

- 内容决策系统
- AI策略系统

GitHub Production 是 Production Execution Engine。

负责：

- 接收 Production Task
- 执行 GitHub Actions
- 调用 Render Workflow
- 运行生产脚本
- 输出 Artifact

历史流程：

```
Production Task File
↓
GitHub Actions
↓
Render Pipeline
↓
Artifact
```

---

# 7. AI Production

AI Gateway Provider：

负责：

- 接收 Production Task
- 调用 AI 生产能力
- 返回 Video Result

流程：

```
Production Task
↓
AI Gateway Provider
↓
AI Model/API
↓
Video Result
```

---

# 8. Video Asset Center

Video Asset Center 是未来统一资产抽象层。

它不是历史 short 视频存储位置。

历史：

```
Artifact
↓
GitHub Pages Media URL
↓
Postiz
```

未来：

```
Production Result
↓
Video Asset Center
↓
Publish Center
```

Video Asset Center 管理：

- Asset Registry
- Asset URL
- 来源记录
- 状态管理
- 生命周期管理

实际文件位置可以是：

- GitHub Artifact
- Cloud Storage
- External Asset URL
- AI Provider Output URL

---

# 9. Legacy vs Future OS

| Layer | Legacy | Future OS |
|---|---|---|
| 内容策略 | Content Strategy | AI Intelligence |
| Task来源 | Task文件 | AI生成Production Task |
| 触发 | workflow_dispatch | 自动调度 |
| 执行 | GitHub Workflow | Provider System |
| 视频产物 | Artifact | Production Result |
| 资产管理 | GitHub Pages URL | Video Asset Center |
| 发布 | Postiz | Publish Center |
| 反馈 | Analytics | Data Center + AI Loop |

---

# 10. Data Center

Data Center 不是普通数据库。

定义：

Production Feedback System。

负责收集：

- Production Result
- Video Asset
- Publish Data
- Analytics Metrics
- Execution Performance

提供给：

AI Intelligence

形成反馈循环。

---

# 11. Phase规划

Phase 15.9C:

AI Production Intelligence Layer

目标：

将：

Legacy:

```
Task文件
↓
人工触发
↓
GitHub执行
```

升级为：

```
Data Center
↓
AI Intelligence
↓
自动Production Task
↓
GitHub Production / AI Production
↓
Feedback Loop
```

目标不是替代 GitHub Production。

目标是增加智能编排层。

---

# 12. 开发原则

保持：

- Legacy GitHub Production兼容
- 双生产架构
- Provider解耦
- Data Feedback Loop
- 本地控制中心

禁止：

- 破坏现有 Production Pipeline
- 直接绑定单一 AI 模型
- 将 Asset Center 等同文件存储
