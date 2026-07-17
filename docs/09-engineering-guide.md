# 工程规范

## 1. 推荐目录

当前项目结构可运行，但正式开发建议逐步演进为：

```text
SoloOps/
  apps/
    api/              FastAPI application
    web/              React console
    worker/           async jobs
  packages/
    domain/           shared domain model and schemas
    contracts/        OpenAPI, event schemas, JSON Schema
  infra/
    compose/
    migrations/
    aliyun/
  docs/
  evals/
  scripts/
  tests/
```

短期不必一次性搬迁；每次重构必须保证现有测试通过。

## 2. 分支与提交

- `main`：始终可运行。
- `feat/<scope>`：新功能。
- `fix/<scope>`：缺陷修复。
- `docs/<scope>`：文档。
- `chore/<scope>`：工程配置。

Commit 使用 Conventional Commits：

```text
feat(scanner): add rds backup rule
fix(executor): reject mutated plan action
docs(architecture): add deployment topology
```

## 3. 代码分层规则

- API 层只做请求解析、鉴权和响应转换。
- Application 层负责用例编排和状态流转。
- Domain 层不依赖 FastAPI、数据库和云 SDK。
- Provider Adapter 封装云 SDK，不把 SDK 类型泄漏到领域层。
- Repository 封装数据库，不在业务代码中散落 SQL。
- Playbook 是唯一写动作入口。

## 4. 测试规范

### 单元测试

覆盖：

- 规则判断。
- 状态流转。
- Playbook 输入校验。
- 权限和审批校验。
- Agent 输出 Schema。

### 集成测试

覆盖：

- API 主链路。
- PostgreSQL Repository。
- Worker Job。
- Mock Provider。
- Dry run Executor。

### E2E 测试

至少一条：

```text
trigger scan -> list findings -> create plan -> execute rejected -> approve -> execute dry run -> query audit
```

## 5. CI 必需检查

```text
format
lint
typecheck
unit tests
integration tests
golden set eval
secret scan
docker build
```

MVP 阶段如果工具尚未全部接入，也要在 README 标注当前可运行的检查命令。

## 6. API 规范

- 新接口必须有 Pydantic 请求和响应模型。
- 错误响应使用统一结构。
- 写接口必须考虑幂等。
- 列表接口必须分页。
- 涉及状态变化的接口必须写审计事件。
- OpenAPI 文档必须能在 `/docs` 查看。

## 7. 数据库规范

- 所有表包含 `created_at` 和必要的 `updated_at`。
- 业务主键使用 UUID。
- 多租户表必须包含 `tenant_id`。
- 审计表只追加，不物理删除。
- 迁移脚本必须可回滚或说明不可回滚原因。
- JSON 字段只用于半结构化证据，不替代核心索引。

## 8. 日志和可观测性

日志字段：

- `timestamp`
- `level`
- `request_id`
- `trace_id`
- `tenant_id`
- `actor_id`
- `action`
- `resource_id`
- `duration_ms`
- `status`

禁止记录：

- AccessKey、Secret、Token。
- 数据库密码。
- Cookie 和 Authorization。
- 未脱敏的用户日志原文。

## 9. ADR 模板

```markdown
# ADR-XXX: 标题

状态：Proposed | Accepted | Superseded

## 背景

## 决策

## 替代方案

## 后果

## 日期
```

以下决策需要 ADR：

- 更换数据库或队列。
- 引入真实写 Playbook。
- 引入新的云 Provider。
- 改变审批策略。
- 引入新的 Agent 框架。

## 10. Definition of Done

一项功能完成必须满足：

- 需求验收标准实现。
- 正常路径和错误路径有测试。
- 权限和审计已覆盖。
- OpenAPI 或前端页面已更新。
- 日志不含敏感信息。
- 涉及 Agent 或 Playbook 时有评测样例。
- 文档同步更新。

## 11. Code Review 重点

- 是否扩大了云权限。
- 是否绕过审批或白名单。
- 是否引入不可追踪的状态变化。
- 是否把云 SDK 类型泄漏到领域层。
- 是否在日志中记录敏感信息。
- 是否缺少错误处理和幂等。
- 是否让 LLM 输出直接影响执行参数。
