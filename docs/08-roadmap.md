# 交付路线图

## 阶段 0：开发前冻结范围（2 天）

- 确认项目定位：阿里云原生可观测与 OOS 之上的 AI 运维治理层，不做任意 Shell。
- 完成编号文档、数据模型、API 契约和安全边界。
- 保留现有 Mock MVP 作为主链路回归基线。
- 准备演示素材：公网数据库、磁盘不足、容器重启三个场景。

## 8 周 MVP

| 周次 | 交付物 | 退出条件 |
| --- | --- | --- |
| W1 | 项目结构升级、PostgreSQL、Repository、迁移脚本 | 当前内存数据迁移到数据库；测试通过 |
| W2 | Scan Job、Worker、资源快照、规则引擎扩展 | 扫描异步化；SG/ECS 规则可回归 |
| W3 | Web Console 基础版：Finding 列表和详情 | 能从页面触发扫描并查看证据 |
| W4 | Remediation Plan、审批流、审计事件 | 未审批执行被拒绝；审批记录可查询 |
| W5 | Playbook Registry、dry run Executor、Verifier | 三个 Playbook 可 dry run 并生成验证结果 |
| W6 | 阿里云原生信号接入：CloudMonitor、ECS 健康、安全组、OOS 执行记录 | 测试账号可读取真实告警/健康事件/资源配置并生成 Finding |
| W7 | Agent 解释、Trace、Golden Set、红队安全测试 | Agent 输出结构化；评测脚本进入 CI |
| W8 | 部署、Demo 数据、录屏脚本、README 完善 | 一键启动、本地演示、线上测试环境可访问 |

## 上线冲刺（W9-W10）

| 周次 | 交付物 | 退出条件 |
| --- | --- | --- |
| W9 | ECS + RDS + Redis + OSS 部署，HTTPS，备份 | 测试域名可访问；数据库可恢复 |
| W10 | 监控告警、安全复核、压测、演示材料 | 发布检查清单通过；准备面试讲解稿 |

## 版本规划

当前实现进度：

- W1：已完成 SQLAlchemy Repository、本地 SQLite、数据库初始化脚本。
- W2：已完成 Mock 原生信号归因、Scan 任务状态机、进程内后台 Worker/队列、Scan/Finding/Plan 查询接口；Redis/Celery/RQ 后续按部署需要替换。
- W3：已完成最小 Web Console，可触发 Mock 归因、查看 Finding 列表、证据详情和审计事件；正式 React Console 后续补。
- W4：已完成 Plan 创建、审批门禁、`audit_events` 表、执行未审批拒绝和基础审计流；后续补拒绝审批、筛选、导出和不可变审计策略。
- W5：已完成 Playbook Registry、三个 dry-run Playbook、dry-run Executor 和 Verifier；真实 OOS/STS 执行 Adapter 后续补。
- W6：已完成真实只读接入：指定 ECS 实例、安全组规则、CloudMonitor 磁盘指标、ECS 健康状态、OOS 执行记录、ActionTrail 变更记录、RDS 实例/白名单、OSS bucket 配置和 SLS 日志模式；后续重点是补真实账号配置、权限预检和 provider 错误可视化。
- W7：已完成 Triage Agent、Qwen/Bailian 适配、确定性 fallback、`agent_runs` Trace、Agent API、控制台解释按钮、Golden Set 和红队安全评测脚本。
- W8：已启动部署与演示阶段；新增 React/Vite Console、多阶段 Docker 构建和 W8 部署资源清单，详见 `docs/w8-deployment-and-demo-plan.md`。

仍为 Mock/待迁移的边界：

- `MockCloudProvider`：仍保留为本地回归基线；真实 `AliyunReadOnlyProvider` 已支持 ECS 实例和安全组规则读取。
- `MockNativeSignalProvider`：仍保留为本地回归基线；真实 `AliyunNativeSignalProvider` 已支持 CloudMonitor 磁盘指标和 ECS 健康状态。
- RDS/OSS：已进入规则引擎；当前 `.env` 仍需要配置 `SOLOOPS_ALIYUN_RDS_INSTANCE_ID` 和 `SOLOOPS_ALIYUN_OSS_BUCKET` 才能按最小权限扫描指定资源。
- SLS/OOS/ActionTrail：已接 SDK；SLS 需要配置 `SOLOOPS_ALIYUN_SLS_PROJECT` 和 `SOLOOPS_ALIYUN_SLS_LOGSTORE` 后才能查询真实日志模式。
- `InProcessScanQueue`：当前适合本地演示，生产可替换为 Redis + RQ/Celery 或云上消息队列。
- `DryRunExecutor`：当前不改云资源，真实执行需要接入 STS 短时写角色和 OOS 模板 Adapter。
- `Verifier`：当前为 dry-run 验证，真实验证需要重新读取 CloudMonitor/ECS/SLS/OOS 证据。
- Web Console：已新增 React/TypeScript/Vite Console；FastAPI 会优先服务 `frontend/dist`，未构建时回退到旧静态 HTML。
- Agent：当前已支持 Finding 级 Triage Agent；Planner/Reviewer/Verifier/Postmortem Agent 后续按 Playbook 和执行数据继续扩展。

### v0.1：离线可信 MVP

- Mock Provider。
- 三条规则。
- Finding -> Plan -> Approval -> Dry Run Execution。
- FastAPI + pytest + Docker Compose。

### v0.2：持久化和控制台

- PostgreSQL Repository。
- Web Console。
- 审计日志。
- 状态筛选和详情页。

### v0.3：阿里云原生信号接入

- 阿里云 CloudMonitor 告警/指标、ECS 健康状态、安全组和 OOS 执行记录。
- 权限预检。
- Provider 错误归一化。
- API 限流和缓存。

### v0.4：受控执行

- Playbook Registry。
- STS 写角色。
- Playbook 与 OOS 模板映射。
- 安全组撤销真实执行或调用已登记 OOS 模板。
- 执行后验证和回滚计划。

### v1.0：秋招展示版

- 完整 Web Console。
- Agent 解释和复盘。
- 评测集和安全红队。
- 线上部署、监控和演示脚本。

## 单人开发优先级

必须优先：

1. 当前主链路不回退。
2. 数据持久化。
3. Web 展示风险证据。
4. 审批和审计。
5. 真实阿里云原生信号 Provider。
6. 部署和演示。

可以后置：

- 多租户商业化。
- 多云支持。
- Kubernetes 接入。
- 高级成本分析。
- 复杂 LLM 多 Agent。
- 真实高风险写动作。

## 面试展示里程碑

| 里程碑 | 可讲能力 |
| --- | --- |
| M1：Mock 闭环 | 领域建模、状态机、测试 |
| M2：数据库和审计 | 企业级数据一致性和可追踪性 |
| M3：Web Console | 前后端协作和产品化 |
| M4：阿里云只读 | 云原生和 IAM 最小权限 |
| M5：受控 Playbook/OOS | 安全自动化、模板治理和幂等执行 |
| M6：Agent + Eval | AI 工程化、评测和安全边界 |

## 范围控制规则

- 任意新功能必须能落到 PRD 中的用户故事。
- 涉及写操作必须先补 Playbook、权限和测试。
- 涉及 LLM 输出必须先补 JSON Schema 和评测样例。
- 涉及监控/告警能力时优先接入 CloudMonitor/ARMS/SLS，不自研通用监控。
- 未完成 W1-W5 前，不启动多云和 Kubernetes。
- 每周至少保留一个可演示版本。
