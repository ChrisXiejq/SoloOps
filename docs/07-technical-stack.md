# 技术栈选型

## 1. 选型原则

- 优先选择秋招面试中容易讲清楚、工程实践认可度高的技术。
- MVP 保持可一人开发，不引入过早复杂的微服务和 Kubernetes。
- 核心链路可本地离线演示，真实云接入通过 Adapter 渐进实现。
- 安全、审计、测试和部署能力优先于花哨的 Agent 效果。

## 2. 推荐技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | React + TypeScript + Vite | 风险看板、审批台、审计查询 |
| UI | Tailwind CSS + shadcn/ui | 快速构建企业级控制台 |
| 后端 API | FastAPI + Pydantic | 与当前代码一致，OpenAPI 友好 |
| 异步任务 | Celery/RQ + Redis | 扫描、执行、验证、Agent 任务 |
| 数据库 | PostgreSQL | 核心业务、审计和状态 |
| 缓存/队列 | Redis / Tair | 任务队列、锁、短期缓存 |
| 对象存储 | MinIO / OSS | 诊断包、导出报告、脱敏日志引用 |
| 云 Provider | 阿里云 Python SDK | ECS、CMS、RDS、OSS、RAM/STS |
| Agent | LangGraph 可选 | 状态图编排；MVP 可先手写状态机 |
| 模型网关 | OpenAI-compatible API 抽象 | 便于替换供应商和 Mock |
| 可观测性 | OpenTelemetry + Prometheus/Grafana 或 SLS | Trace、指标、日志 |
| 部署 | Docker Compose on ECS | 单机企业级部署路径 |
| CI | GitHub Actions / 本地脚本 | 测试、构建、扫描 |

## 3. 后端技术细节

### FastAPI

保留当前 FastAPI 作为核心 API 框架，优势：

- Pydantic Schema 与 OpenAPI 自动生成。
- 易于编写 TestClient 集成测试。
- 对异步接口和依赖注入支持较好。
- Python 生态适合云 SDK、Agent 和数据处理。

### PostgreSQL

替代当前 `MemoryStore`，用于：

- Finding 生命周期。
- 审批和审计。
- 资源快照索引。
- Agent Trace 元数据。

后续如需要向量检索，可加 `pgvector`，但 MVP 不强依赖。

### Redis

用于：

- Worker 队列。
- 扫描任务锁。
- 幂等键缓存。
- Provider API 限流。

Redis 中不保存长期业务事实。

## 4. 云接入

首期真实接入阿里云：

- ECS：实例、安全组、安全组规则。
- CloudMonitor：磁盘、CPU、网络等指标。
- RDS：实例、备份、备份策略。
- OSS：Bucket ACL、生命周期和对象前缀策略。
- RAM/STS：只读角色和审批后短时写角色。

Provider 接口需要隐藏云厂商差异，后续可添加腾讯云、AWS 或本地 Docker Provider。

## 5. 前端页面技术

前端只做控制台，不做复杂动画：

- 首页：风险数量、严重级别、待审批。
- Finding 列表：筛选、排序、状态。
- Finding 详情：证据、解释、计划入口。
- Plan 详情：影响、回滚、审批。
- Audit：时间线和导出。
- Settings：Provider、成员、阈值。

所有写操作需要二次确认；高风险执行按钮必须展示计划摘要。

## 6. Agent 技术路线

MVP：

- 模板化解释。
- 确定性 Planner。
- JSON Schema 校验。
- Mock LLM Gateway。

进阶：

- LangGraph 状态图。
- LLM 生成解释和复盘摘要。
- 成本、延迟、错误率统计。
- Prompt 版本和评测集。

不建议首版直接引入复杂多 Agent 群聊，面试时也更难解释安全边界。

## 7. 本地开发依赖

```text
Python 3.11+
Node.js 20+
Docker Desktop
PostgreSQL 15+
Redis 7+
MinIO
```

当前原型只需要 Python + FastAPI 即可运行；进入正式开发后再逐步补齐 Web、DB 和 Worker。

## 8. 不采用的方案

| 方案 | 暂不采用原因 |
| --- | --- |
| Kubernetes 首发部署 | 单人开发和秋招展示成本过高 |
| 自研监控存储 | 偏离项目核心，CloudMonitor/Prometheus 足够 |
| 任意 Shell Agent | 安全不可控，不适合企业级叙事 |
| 全多云首发 | 范围过大，Provider 接口先预留 |
| 从零训练模型 | 与项目目标无关，成本高 |

## 9. 技术亮点

- FastAPI + OpenAPI 的清晰后端契约。
- Provider Port/Adapter 的云厂商解耦。
- Rule Engine + Playbook 的确定性安全底座。
- Agent 输出 Schema 和评测体系。
- RAM/STS 最小权限和审批后短时写权限。
- 审计链路、幂等执行和执行后验证。
