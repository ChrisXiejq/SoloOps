# 交付路线图

## 阶段 0：开发前冻结范围（2 天）

- 确认项目定位：AI 应用运维副驾，不做任意 Shell。
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
| W6 | 阿里云只读 Provider：ECS、安全组、CloudMonitor | 测试账号可读取真实资源并生成 Finding |
| W7 | Agent 解释、Trace、Golden Set、红队安全测试 | Agent 输出结构化；评测脚本进入 CI |
| W8 | 部署、Demo 数据、录屏脚本、README 完善 | 一键启动、本地演示、线上测试环境可访问 |

## 上线冲刺（W9-W10）

| 周次 | 交付物 | 退出条件 |
| --- | --- | --- |
| W9 | ECS + RDS + Redis + OSS 部署，HTTPS，备份 | 测试域名可访问；数据库可恢复 |
| W10 | 监控告警、安全复核、压测、演示材料 | 发布检查清单通过；准备面试讲解稿 |

## 版本规划

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

### v0.3：真实云只读巡检

- 阿里云 ECS、安全组和 CloudMonitor。
- 权限预检。
- Provider 错误归一化。
- API 限流和缓存。

### v0.4：受控执行

- Playbook Registry。
- STS 写角色。
- 安全组撤销真实执行。
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
5. 真实只读 Provider。
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
| M5：受控 Playbook | 安全自动化和幂等执行 |
| M6：Agent + Eval | AI 工程化、评测和安全边界 |

## 范围控制规则

- 任意新功能必须能落到 PRD 中的用户故事。
- 涉及写操作必须先补 Playbook、权限和测试。
- 涉及 LLM 输出必须先补 JSON Schema 和评测样例。
- 未完成 W1-W5 前，不启动多云和 Kubernetes。
- 每周至少保留一个可演示版本。
