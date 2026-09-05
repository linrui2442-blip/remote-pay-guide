# Remote Pay Guide OS Blueprint v2

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

## 2. 总体系统架构

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

              Video Asset Center

                        |
                        ↓

                 Publish Center

                        |
                        ↓

                   Analytics

                        |
                        ↓

                  Data Center

                        |
                        ↓

               AI Intelligence
```

---

## 3. AI Intelligence

AI Intelligence 是系统智能决策层。

职责：

1. 分析 Data Center 数据
2. 生成生产策略
3. 生成 Production Task
4. 选择生产线路
5. 优化未来生产流程

AI Intelligence 不直接执行生产。

它负责决策，Production 负责执行。

---

## 4. Production Task

Production Task 是 AI Intelligence 输出给 Production 系统的生产执行指令。

不是：

- 用户手动视频任务
- GitHub 生成任务

包含：

- production objective
- provider selection
- execution parameters
- template/configuration
- input resources

流程：

```
AI Intelligence

↓

Production Task

↓

Production Execution
```

---

## 5. 双生产线路

Production Task 进入 Provider Selection。

### GitHub Production

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

GitHub 不负责：

- 决策
- 内容理解
- 生产策略生成

GitHub 负责：

- 接收 Production Task
- 调用 Workflow
- 执行生产
- 返回 Artifact

---

### AI Production

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

AI Gateway Provider 负责：

- 接收 Production Task
- 调用 AI 生产能力
- 返回生产结果

---

## 6. Video Asset Center

Video Asset Center 不是本机文件存储。

它是线上视频资产管理中心。

职责：

- Asset Registry
- Asset URL 管理
- 来源记录
- 状态管理
- 生命周期管理

统一接收：

- GitHub Video Artifact
- AI Video Result

结构：

```
Production Result

↓

Video Asset Center

↓

Publish Center
```

实际文件位置可以是：

- GitHub Artifact
- Cloud Storage
- External Asset URL
- AI Provider Output URL

Asset Center 管理的是引用关系和生命周期。

---

## 7. Publish Center

Publish Center 不关心视频来源。

只接收 Video Asset。

流程：

```
Video Asset

↓

Publish Center

↓

Postiz

↓

Platform
```

---

## 8. Data Center

Data Center 不是普通数据库。

定义：

Production Feedback System。

负责收集：

- Production Result
- Video Asset
- Publish Data
- Analytics Metrics
- Execution Performance

并提供给：

AI Intelligence

形成反馈循环。

---

## 9. Feedback Loop

```
Production

↓

Asset

↓

Publish

↓

Analytics

↓

Data Center

↓

AI Intelligence

↓

New Production Strategy
```

---

## 10. Phase 规划

Phase 15.9C:

原：Prompt Optimization

更新为：

AI Production Intelligence Layer

目标：

实现：

```
Data Center

↓

AI Intelligence

↓

Production Task Generation

↓

GitHub Production / AI Production

↓

Feedback Loop
```

---

## 11. 开发原则

保持：

- GitHub 原生产线路
- 双生产架构
- Provider 解耦
- Data Feedback Loop
- 本地控制中心

禁止：

- 破坏现有 Production Pipeline
- 直接绑定单一 AI 模型
- 将 Asset Center 等同文件存储
