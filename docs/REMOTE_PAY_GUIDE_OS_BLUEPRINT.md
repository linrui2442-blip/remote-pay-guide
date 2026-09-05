# Remote Pay Guide OS Blueprint

## 1. 项目定位

Remote Pay Guide OS 是运行在本地电脑的个人内容运营操作系统。

目标：

统一管理：

- 视频生产
- 视频资产
- 视频发布
- 平台数据
- Analytics分析

---

## 2. 总体架构

Remote Pay Guide OS

本地控制中心

三个核心中心：

1. Production Center
生产中心

2. Publish Center
发布中心

3. Data Center
数据中心

---

## 3. Production Center

生产中心包含两个平级生产线：

### GitHub Actions

负责：

- 现有视频生产workflow
- Render
- Artifact
- 自动化生产

### Local AI Pipeline

负责：

- 本地AI生成
- 外部AI工具接入
- 第二生产线

两者关系：

GitHub Actions ≠ Local AI Pipeline

二者平级。

统一输出：

Video Asset

---

## 4. Publish Center

发布中心负责统一调度视频发布。

核心：

Publish Engine

输入：

Video Asset

输出：

平台发布任务。

支持未来：

- YouTube
- TikTok
- Instagram
- Facebook

发布中心替代第三方发布依赖。

---

## 5. Data Center

数据中心负责平台数据获取和分析。

包含两个平级模块：

Analytics API

Platform Data

Analytics API:

负责：

- 调用平台接口
- 获取数据

Platform Data:

负责：

- 保存平台返回数据
- 分析数据

---

## 6. 数据流

生产：

GitHub Actions
+
Local AI Pipeline

↓

Video Asset

↓

Publish Center

↓

Platform API

↓

Analytics API

↓

Database

↓

Dashboard

---

## 7. 数据库规划

第一阶段：

SQLite

核心数据：

- videos
- publish_tasks
- analytics
- accounts

---

## 8. 开发原则

必须保持：

- GitHub生产线继续使用
- 不重新设计视频生成流程
- 不依赖服务器
- 本地运行控制中心
- 低成本

---

## 9. 开发阶段

Phase 15.1:

Local OS Backend Skeleton

Phase 15.2:

GitHub Actions Integration

Phase 15.3:

Video Asset Management

Phase 15.4:

Publish Engine

Phase 15.5:

Analytics Center

Phase 15.6:

AI Optimization
