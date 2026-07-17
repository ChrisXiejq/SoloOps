# SoloOps 文档索引

这组文档是 SoloOps 进入实际开发前的基线，参考 RedFlow 的编号结构组织。旧版 `architecture.md`、`feasibility.md`、`iam.md` 仍保留为早期调研材料；正式开发优先阅读编号文档。

## 推荐阅读顺序

| 文档 | 说明 |
| --- | --- |
| [00-project-charter.md](00-project-charter.md) | 项目愿景、用户、范围、成功标准和风险 |
| [01-prd.md](01-prd.md) | 用户故事、功能需求、状态和页面信息架构 |
| [02-architecture.md](02-architecture.md) | 系统架构、模块职责、时序、部署拓扑 |
| [03-agent-playbook-design.md](03-agent-playbook-design.md) | Agent 分工、Playbook 契约和安全边界 |
| [04-data-api-design.md](04-data-api-design.md) | 核心实体、表设计、API 契约和事件 |
| [05-safety-compliance.md](05-safety-compliance.md) | 权限、审批、执行、审计和 LLM 安全 |
| [06-evaluation.md](06-evaluation.md) | Golden Set、红队样例、测试和发布门禁 |
| [07-technical-stack.md](07-technical-stack.md) | 技术栈选型、云接入、前端和 Agent 路线 |
| [08-roadmap.md](08-roadmap.md) | 8 周 MVP、上线冲刺、版本规划和优先级 |
| [09-engineering-guide.md](09-engineering-guide.md) | 目录、提交、分层、测试、CI 和 DoD |
| [10-demo-story.md](10-demo-story.md) | 秋招演示脚本、讲解重点和简历描述 |
| [11-deployment-runbook.md](11-deployment-runbook.md) | 本地、生产部署、发布检查、回滚和故障处理 |
| [12-resource-and-cost-plan.md](12-resource-and-cost-plan.md) | Conda 环境、阿里云资源、模型资源和成本规划 |

## 开发前必须冻结的决策

- SoloOps 默认只读，不做任意 SSH/Shell。
- 规则引擎生成 Finding，LLM 只做解释和辅助计划。
- 写动作必须来自 Playbook Registry。
- 执行必须经过人工审批、最小权限、幂等校验和执行后验证。
- Mock Provider 是长期保留的演示和测试基线。

## 下一步开发建议

1. 先把当前内存仓库替换为 PostgreSQL Repository。
2. 增加扫描任务状态和 Worker。
3. 开发 Web Console 的 Finding 列表和详情页。
4. 完成审批、审计和 dry run 执行的持久化。
5. 再接入阿里云只读 Provider。
