# Remote Pay Guide OS Blueprint v2.2

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
Analytics
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

## 9. Data Feedback Loop

Data Center 收集：

- Production Result
- Video Asset
- Publish Data
- Analytics Metrics
- Execution Performance

提供给 AI Intelligence，形成反馈循环。

---

## 10. 开发原则

保持：

- Legacy GitHub Production 兼容
- 双生产架构
- Provider 解耦
- Data Feedback Loop
- 本地控制中心

禁止：

- 破坏现有 Production Pipeline
- 将系统设计为本地 AI 推理工作站
- 绑定单一 AI 模型
- 将 Asset Center 等同文件存储

术语统一：

使用：

- AI Remote Production Line
- AI Gateway Production Line

避免使用会误导为本地模型推理的“Local AI Production Line”。
