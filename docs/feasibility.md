# 阿里云可行性与授权边界调研

## 结论

SoloOps 的 MVP 与后续线上版本在阿里云上具有完整可行性，前提是采用 RAM 最小权限和审批后短时写权限。阿里云提供：

- ECS 安全组作为可读取、可按权限变更的网络访问控制面；安全组规则控制实例入/出站流量。[安全组规则](https://help.aliyun.com/zh/ecs/user-guide/security-group-rules/)
- CloudMonitor 的 `DescribeMetricList` 等指标查询 API，用于读取云服务指标；存在调用配额和频率限制，应由缓存/限流保护。[DescribeMetricList](https://help.aliyun.com/en/cms/cloudmonitor-1-0/developer-reference/api-cms-2019-01-01-describemetriclist)
- RDS API，包括实例、性能、慢日志、备份集、备份策略和恢复相关查询/操作。[RDS API 概览](https://help.aliyun.com/zh/rds/list-of-operations-by-function)
- OSS 基于 RAM Policy 的细粒度对象/前缀权限；默认拒绝和显式拒绝优先，适合巡检角色最小授权。[OSS RAM Policy](https://help.aliyun.com/zh/oss/user-guide/ram-policy/)
- STS 临时凭证，可对角色和本次会话进一步限制权限，适合把读角色与写角色隔离。[STS](https://help.aliyun.com/zh/ram/user-guide/what-is-sts)

因此，SoloOps 应优先读取阿里云原生信号与资源状态：CloudMonitor 指标/告警、ECS 健康状态、SLS 摘要、OOS 执行记录、资源配置、账单和备份状态。**重启实例、修改安全组、创建备份、改变数据库/对象存储策略**只能由独立的审批后执行通道完成，必要时调用已登记的 OOS 模板。

## 可实现能力矩阵

| 能力 | 技术可行性 | MVP | 授权策略 |
| --- | --- | --- | --- |
| ECS/安全组盘点 | 可行 | 是 | 只读 RAM Role |
| CPU/磁盘/网络指标与告警 | 可行 | Mock，后续接 CMS/CloudMonitor | 只读 RAM Role + API 限流 |
| Docker/应用日志 | 可行 | 后续 Agent 采集器 | 仅本机受限日志读取，不给通用 shell |
| RDS 备份健康检查 | 可行 | 后续 | RDS DescribeBackups/DescribeBackupPolicy 只读 |
| OSS 公共访问/生命周期检查 | 可行 | 后续 | 指定 bucket 的只读策略 |
| 账单/异常成本解释 | 可行 | 后续 | 费用与成本只读接口/导出；账单有时间延迟 |
| 关闭风险安全组规则 | 可行 | Mock dry run | 人工审批 + 单次短时 write role 或已登记 OOS 模板 |
| 重启容器/实例 | 可行但高风险 | 不做自动执行 | 人工审批 + 固定 Playbook + 验证/回滚 |
| 任意 SSH/Shell | 技术上可行但不可接受 | 否 | 永不提供给模型 |

## 重要限制

1. 云 API、地区、账号类型和资源规格会影响可用能力，生产接入前必须在 OpenAPI Explorer 与测试账号验证。
2. CloudMonitor API 有免费额度/频率限制；项目必须缓存指标，按资源批量拉取，不进行高频 Agent 轮询。
3. 账单并非实时数据，成本 Agent 必须标注“统计截至时间”，不能把延迟账单当实时告警。
4. RDS 备份的“存在”不等于“可恢复”；SoloOps 后期应建立到临时实例的恢复演练，但不在生产库上直接恢复。
5. 变更操作应由确定性 Playbook 执行，模型只能提出计划；不让 LLM 自由组合 API 参数。

## 首版验收

- 在无阿里云密钥条件下通过 Mock 场景演示完整审批链。
- 配置只读角色后，能展示真实 ECS 实例、安全组和至少一个 CloudMonitor 告警/指标信号。
- 禁止无审批执行，禁止任何未白名单动作。
- 对每次读取/计划/批准/执行保存 `trace_id`、用户、资源、动作、时间和结果。
