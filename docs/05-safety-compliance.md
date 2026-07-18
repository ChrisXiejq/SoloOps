# 安全与合规设计

## 1. 安全目标

SoloOps 处理的是云资源和运维动作，安全目标优先级高于自动化程度：

- 默认只读，不因模型输出改变资源。
- 写权限短时、单动作、单资源、可审计。
- 所有高风险动作必须人工审批。
- 任何执行都可追溯到 Finding、计划、审批和验证。
- 日志、Trace、评测数据不泄露密钥和敏感业务数据。

## 2. 威胁模型

| 威胁 | 场景 | 防护 |
| --- | --- | --- |
| 权限过大 | 应用持有主账号 AccessKey | RAM Role、STS、读写分离、无长期密钥 |
| Prompt 注入 | 日志或资源标签诱导 Agent 执行命令 | Agent 不具备执行自由文本能力，工具 Schema 校验 |
| 越权执行 | 用户绕过审批直接调用执行接口 | 服务端校验审批、角色、白名单、幂等键 |
| 参数篡改 | 审批后修改目标资源或动作 | 执行时重新比对计划、审批和 Finding 证据 |
| 审计缺失 | 变更后无法定位责任 | 不可变 Audit Event，记录 actor、resource、action |
| 敏感信息泄露 | Trace 写入 AccessKey、日志原文 | 日志脱敏、字段黑名单、对象存储访问控制 |
| 误修复 | Playbook 影响合法流量 | Precheck、影响说明、审批问题、执行后验证和回滚 |

## 3. 权限模型

### 3.1 应用角色

| 角色 | 能力 |
| --- | --- |
| Owner | 管理工作区、Provider、成员、执行开关 |
| Operator | 触发扫描、查看 Finding、创建计划 |
| Approver | 审批或拒绝计划、查看审计 |
| Viewer | 只读查看风险和审计 |

### 3.2 云角色

| 云角色 | 使用阶段 | 权限 |
| --- | --- | --- |
| `soloops-read-role` | 扫描、验证 | Describe/List/Get |
| `soloops-write-role` | 审批后执行 | 单 Playbook 所需最小写权限 |
| `soloops-deploy-role` | 部署 | 拉镜像、更新服务、读取配置 |

应用不得保存主账号 AccessKey；真实生产使用 RAM Role 和 STS 临时凭证。

## 4. 审批控制

- `critical` 和 `high` 风险的写动作必须审批。
- 审批人和计划创建人默认不能是同一人；单人演示模式可以配置放宽，但 UI 必须标记。
- 审批记录不可编辑，只能追加新决策。
- 审批后执行参数不可变；如需修改，必须创建新计划。
- 审批过期时间默认 30 分钟，过期后需要重新审批。

## 5. 执行安全

Executor 必须按顺序校验：

1. Plan 存在且状态为 `APPROVED`。
2. Approval 存在且未过期。
3. 当前用户有执行权限。
4. Action 在 Playbook Registry 中。
5. Playbook 输入与 Finding 证据匹配。
6. 幂等键未被成功使用。
7. STS 写角色只包含本动作需要的权限。
8. 执行后 Verifier 重新读取资源状态。

禁止能力：

- 任意 SSH。
- 任意 Shell。
- 任意文件删除。
- 任意云 API 代理。
- 模型直接访问凭证。
- 关闭审计、告警或权限校验。

## 6. 数据安全

| 数据 | 存储策略 |
| --- | --- |
| 云资源元数据 | MySQL，按租户隔离 |
| 指标和配置证据 | MySQL 摘要，必要时对象存储引用 |
| 原始日志片段 | 默认不存；如保存，脱敏后进私有 OSS |
| STS Token | 只在内存使用，不落库 |
| 审批和审计 | MySQL，不物理删除 |
| Trace | 保存摘要、模型、工具和成本，不保存密钥 |

敏感字段黑名单：`access_key`、`secret`、`token`、`password`、`authorization`、`cookie`、`private_key`。

## 7. LLM 安全

- LLM 输入只包含必要证据和脱敏摘要。
- LLM 输出必须通过 JSON Schema 校验。
- LLM 不产生执行动作，只能引用已有 Playbook ID。
- LLM 置信度不能作为审批依据，只能辅助阅读。
- Prompt 中明确禁止编造证据、建议绕过权限、生成破坏性命令。

## 8. 合规和审计

每个审计事件至少包含：

- `event_id`
- `tenant_id`
- `actor_id`
- `actor_role`
- `entity_type`
- `entity_id`
- `action`
- `resource_id`
- `request_id`
- `trace_id`
- `created_at`
- `payload_hash`

审计查询支持按时间、用户、资源、动作和结果过滤。导出审计报告时默认脱敏。

## 9. 安全测试清单

- 未登录访问 API 被拒绝。
- Viewer 不能创建计划。
- Operator 不能审批高风险计划。
- 未审批计划不能执行。
- 审批后篡改 action 被拒绝。
- 非白名单 action 被拒绝。
- 重复幂等键不会重复执行。
- 执行开关关闭时只 dry run。
- 日志中不出现密钥关键字。
- Prompt 注入样例不能触发执行。
