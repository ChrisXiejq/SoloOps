# Demo Story：秋招项目演示脚本

## 1. 演示目标

用 8-10 分钟展示 SoloOps 不是普通 CRUD，也不是 CloudMonitor/OOS 的替代品，而是一个具备企业级边界的 AI 运维治理系统：

- 能接入和归并阿里云原生告警、健康事件和资源配置。
- 能解释证据和影响。
- 能生成受控修复计划。
- 能通过人工审批执行。
- 能保存审计和验证结果。

## 2. 演示场景

假设有一个独立开发者运行了一个线上应用：

- Web 服务跑在 ECS 上。
- 数据库使用 MySQL/宝塔 MySQL/RDS MySQL。
- 应用通过 Docker Compose 部署。
- 最近 CloudMonitor 出现磁盘告警，SLS 里出现容器重启日志。
- 安全组错误地把 PostgreSQL 暴露到公网。

Mock 数据中对应：

- `sg-redflow-db`：公网开放 `TCP/5432`。
- `i-soloops-demo`：磁盘使用率 91%。
- `i-soloops-demo`：容器重启 7 次。

## 3. 演示流程

### Step 1：项目定位

讲解：

> SoloOps 是面向小团队的 AI 运维治理层。它不是替代阿里云 CloudMonitor、ARMS、SLS 或 OOS，而是把这些原生告警、健康事件和执行模板治理成可解释、可审批、可验证、可审计的修复闭环。

展示：

- README。
- 架构图。
- `/docs` OpenAPI。

### Step 2：触发扫描

命令：

```bash
curl -X POST http://localhost:8000/api/v1/scans \
  -H 'Content-Type: application/json' \
  -d '{"provider":"mock"}'
```

讲解：

> 当前使用 Mock Provider，真实接入时会读取 CloudMonitor 告警/指标、ECS 健康状态、安全组配置、SLS 摘要和 OOS 执行记录。归因阶段只读，不具备写权限。

### Step 3：查看 Findings

命令：

```bash
curl http://localhost:8000/api/v1/findings
```

重点展示：

- SG-001：公网 PostgreSQL。
- ECS-001：磁盘空间不足。
- ECS-002：容器重启异常。

讲解：

> 每个 Finding 都有 rule_id、severity、resource_id 和 evidence。面试时可以强调：阿里云原生系统负责发现信号，SoloOps 负责归并证据、解释风险和治理修复闭环。

### Step 4：生成修复计划

对 SG-001 创建计划：

```bash
curl -X POST http://localhost:8000/api/v1/findings/<finding_id>/plans
```

展示计划字段：

- action：`revoke_public_postgres_rule`
- target：`sg-redflow-db`
- expected_impact
- rollback

讲解：

> 计划只能来自白名单 Playbook。LLM 即使参与，也只能解释和补充风险，不能发明一个新动作。

### Step 5：未审批执行被拒绝

命令：

```bash
curl -X POST http://localhost:8000/api/v1/plans/<plan_id>/execute
```

预期：

```json
{
  "detail": "Human approval is required"
}
```

讲解：

> 这是项目最重要的安全边界之一：没有审批，执行不会发生。

### Step 6：审批后 dry run

命令：

```bash
curl -X POST http://localhost:8000/api/v1/plans/<plan_id>/approve \
  -H 'Content-Type: application/json' \
  -d '{"approver":"owner","comment":"confirmed for demo"}'

curl -X POST http://localhost:8000/api/v1/plans/<plan_id>/execute
```

预期：

```json
{
  "status": "succeeded",
  "verification": "Dry run completed; no cloud resource was changed.",
  "audit": [
    "approval verified",
    "execution disabled by SOLOOPS_EXECUTION_ENABLED"
  ]
}
```

讲解：

> 默认执行开关关闭，所以演示环境不会修改任何云资源。真实环境中执行器会使用短时写角色，而且只能执行这个 Playbook 的单个动作。

### Step 7：讲架构与安全

展示：

- `docs/02-architecture.md`
- `docs/05-safety-compliance.md`
- `docs/03-agent-playbook-design.md`

讲解重点：

- Provider Port/Adapter 解耦云厂商。
- Rule Engine 负责确定性 Finding。
- Playbook Registry 控制执行动作。
- Approval Gate 防止越权。
- Verifier 执行后重新读取证据。
- Audit/Trace 支撑复盘。

## 4. 面试问答准备

### 为什么不用模型直接执行命令？

因为运维动作有高风险。SoloOps 把模型限制在解释和计划辅助，执行必须走确定性 Playbook、审批和最小权限。

### 和普通监控系统有什么区别？

普通监控主要负责采集和告警；SoloOps 不重复做这件事。它消费 CloudMonitor/ARMS/SLS/ECS/OOS 的原生信号，增加证据化 Finding、修复计划、审批、受控执行和审计闭环。

### 如何接入真实阿里云？

实现阿里云只读 Signal Provider，读取 CloudMonitor 告警/指标、ECS 健康和安全组、SLS 摘要、OOS 模板和执行记录；写动作使用单独 ExecutionAdapter，可调用已登记 OOS 模板，并通过 RAM/STS 获取短时写权限。

### 如何避免误操作？

默认只读；写动作白名单；审批后参数不可变；执行前比对 Finding 证据；执行后验证；审计不可变。

### 项目难点是什么？

难点不是调云 API，而是把 Agent、权限、状态机、审计和运维 Playbook 做成可控系统。

## 5. 演示数据准备

本地演示前确认：

```bash
pytest
docker compose up --build
```

打开：

- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/healthz`

## 6. 简历描述

可写为：

> SoloOps：面向独立开发者和小团队的 AI 运维治理层。基于 FastAPI、MySQL、Redis、Docker 和阿里云 RAM/STS 设计，聚合 CloudMonitor、ECS 健康、SLS、OOS 等原生信号，将告警转化为证据化 Finding、受控 Playbook/OOS 模板、人工审批、dry-run 执行、审计追踪和 Agent 风险解释。项目强调最小权限、状态机、可观测性、评测体系和 LLM 安全边界。
