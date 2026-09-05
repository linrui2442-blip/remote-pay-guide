# Remote Pay Guide OS Blueprint v2

## 1. 项目定位更新

Remote Pay Guide OS 是运行在本地电脑的个人内容生产与运营操作系统。

系统目标：

统一管理：

- 内容生产决策
- 视频生产执行
- 视频资产管理
- 视频发布
- 平台数据反馈
- AI Intelligence 决策优化

---

## 2. 核心架构

Remote Pay Guide OS v2

```
Data Center
      ↓
Analytics Feedback
      ↓
AI Intelligence
      ↓
Production Task
      ↓
Production Provider Selection
      ↓
Production Pipeline
      ↓
Production Result
      ↓
Video Asset Center
      ↓
Publish Center
      ↓
Platform Analytics
      ↓
Data Center Feedback Loop
```

---

## 3. Production Center

Production Center 保留双生产线路。

### 原生产线路：GitHub Production

职责：

- 接收 Production Task
- 调用 GitHub Actions
- 执行 Render Workflow
- 生成 Video Artifact
- 返回 Production Result

流程：

```
Production Task
      ↓
GitHub Provider
      ↓
GitHub Actions
      ↓
Render Workflow
      ↓
Video Artifact
```

### 新生产线路：AI Production

职责：

- 接收 Production Task
- 调用 AI Gateway Provider
- 执行 AI 生产流程
- 返回 AI Result

流程：

```
Production Task
      ↓
AI Gateway Provider
      ↓
AI Production Model
      ↓
Video Result
```

两条线路平级：

```
GitHub Production ≠ AI Production
```

统一输出：

```
Production Result
      ↓
Video Asset Center
```

---

## 4. Production Task 定义更新

Production Task 不再定义为简单的视频生成任务。

新的定义：

> AI Intelligence 或系统策略生成的生产执行指令。

Production Task 包含：

- production objective
- provider choice
- execution parameters
- template/configuration
- input resources

Production Task 是连接：

```
AI Decision Layer
        ↓
Production Execution Layer
```

的桥梁。

---

## 5. Provider 定义更新

Provider 只负责执行，不负责生产决策。

### GitHub Provider

负责：

- 接收 Production Task
- 调用 GitHub Actions
- 触发 Render Workflow
- 获取 Artifact

### AI Gateway Provider

负责：

- 接收 Production Task
- 调用 AI Gateway
- 执行 AI 生产
- 返回 Result

---

## 6. Data Center 定义更新

Data Center 不只是数据存储。

定位：

Production Feedback System

负责收集：

- Production Result
- Runtime Execution
- Video Asset
- Publish Data
- Analytics Metrics
- Provider Performance

并向 AI Intelligence 提供决策输入。

---

## 7. AI Intelligence 定义更新

AI Intelligence 是系统智能决策层。

包含：

### Analytics Intelligence

分析：

- 生产结果
- 发布结果
- 系统效率
- 内容表现

### Decision Intelligence

生成：

- Production Strategy

### Production Planning

生成：

- Production Task

### Optimization Intelligence

优化：

- Provider 选择
- Workflow 策略
- 生产参数

---

## 8. 完整生产闭环

```
Data Center
      ↓
Analytics Feedback
      ↓
AI Intelligence
      ↓
Production Task
      ↓
Production Provider Selection

        ┌────────────────┐
        │                │
        ↓                ↓

GitHub Production   AI Production

        │                │
        ↓                ↓

GitHub Provider    AI Gateway Provider

        │                │
        ↓                ↓

Artifact           AI Result

        └────────────────┘
                 ↓

        Production Result
                 ↓
        Video Asset Center
                 ↓
        Publish Center
                 ↓
        Platform Analytics
                 ↓
        Data Center
```

---

## 9. Phase 规划更新

原：

Phase 15.9C Prompt Optimization

调整为：

Phase 15.9C AI Production Intelligence Layer

目标：

建立：

```
Data Center
      ↓
AI Intelligence
      ↓
Production Task Generation
      ↓
GitHub Production
      ↓
AI Production
```

形成自动生产反馈闭环。

---

## 10. 开发原则

保持：

- GitHub 原生产流程
- 双生产线路
- 本地控制中心
- Provider 解耦
- Data Feedback Loop

禁止：

- 破坏现有 GitHub Production
- 重建生产链路
- 引入不必要服务器依赖

---

版本：

Remote Pay Guide OS Blueprint v2
