# SoloOps

> 面向独立开发者和小团队的 AI 运维治理层：聚合阿里云原生监控、健康事件和 OOS 自动化能力，将告警转化为可解释、可审批、可验证、可审计的修复闭环。

SoloOps 不替代阿里云 CloudMonitor、ARMS、SLS、ECS 健康检查或 OOS。它站在这些原生能力之上，负责把监控告警、资源配置、部署上下文和团队策略组织成 Finding；只有经过人工批准且命中受限 Playbook 的操作才允许执行。项目刻意不包含任意 SSH、任意 Shell 或模型直接修改云资源的能力。

## 当前实现

- FastAPI 服务与 OpenAPI 文档。
- 可离线运行的 `MockCloudProvider`：模拟 ECS、安全组、RDS 和 OSS 资源发现。
- 面向阿里云原生生态的治理层设计：CloudMonitor/ARMS/SLS 作为信号源，OOS 作为可选执行后端。
- 可离线运行的 `MockNativeSignalProvider`：模拟 CloudMonitor 告警、SLS 日志模式和 OOS 执行记录。
- 真实阿里云只读 Provider：已接入指定 ECS 实例、安全组规则、RDS 实例/白名单、OSS bucket ACL/加密、CloudMonitor 磁盘指标、ECS 健康状态、OOS 执行记录、ActionTrail 变更记录和 SLS 日志模式。
- 八条确定性巡检规则：公网暴露 PostgreSQL、磁盘空间不足、容器反复重启、RDS 公网白名单、RDS 备份关闭、RDS 存储高水位、OSS 公共访问、OSS 未启用服务端加密；其中容器重启可由 SLS 日志模式触发。
- Scan 任务状态机：`pending -> running -> succeeded/failed`。
- 进程内后台 Worker/队列：API 先返回 `pending` scan，Worker 执行后前端轮询查询结果。
- Finding → Remediation Plan → Approval → Execution 的受控状态机。
- 审计事件表：记录扫描请求、运行、成功/失败、计划、审批和执行结果。
- W7 Agent 能力：Triage Agent 基于 Finding 证据生成结构化解释、影响分析、安全下一步和人工问题；结果保存为 `agent_runs` Trace，支持 Qwen/Bailian 和确定性 fallback。
- Playbook Registry、dry-run Executor 和 Verifier：默认安全 dry run；开启 `SOLOOPS_EXECUTION_ENABLED=true` 后，仅 `revoke_public_postgres_rule` 会按 Finding 证据撤销精确匹配的公网 TCP/5432 入站规则，随后重新读取安全组验证。
- SQLAlchemy Repository：本地默认 SQLite，生产可切换 RDS PostgreSQL。
- React/TypeScript Console：触发 Mock/Aliyun 扫描、查看 Finding/证据、生成 Agent 解释、创建 Plan、查看审计事件和原生信号；未构建 React 时回退到旧静态页面。
- 动作白名单与审批令牌校验；执行器当前为安全的 mock，真实阿里云执行器需单独接入。
- Docker Compose 本地环境、pytest 测试、部署/IAM/可行性文档。

## 快速开始

```bash
cp .env.example .env
docker compose up --build
```

打开 Web Console：`http://localhost:8000/`。

本地开发 React Console：

```bash
cd frontend
npm install
npm run dev
```

另一个终端启动 API：

```bash
uvicorn app.api:app --reload
```

打开 `http://localhost:5173`。构建后由 FastAPI 托管：

```bash
cd frontend
npm run build
cd ..
uvicorn app.api:app --reload
```

打开 OpenAPI：`http://localhost:8000/docs`，或运行：

```bash
curl -X POST http://localhost:8000/api/v1/scans \
  -H 'Content-Type: application/json' \
  -d '{"provider":"mock"}'
curl -X POST http://localhost:8000/api/v1/scans \
  -H 'Content-Type: application/json' \
  -d '{"provider":"aliyun"}'
curl http://localhost:8000/api/v1/findings
curl -X POST http://localhost:8000/api/v1/findings/{finding_id}/agent-runs
curl http://localhost:8000/api/v1/agent-runs
curl http://localhost:8000/api/v1/audit-events
curl http://localhost:8000/api/v1/playbooks
```

运行本地测试：

```bash
source /Users/bytedance/my/.conda-base/etc/profile.d/conda.sh
conda activate /Users/bytedance/my/.conda-envs/soloops
pytest
python scripts/run_agent_eval.py
```

如果需要重建 Conda 环境：

```bash
conda env create -f environment.yml
conda activate soloops
```

初始化本地数据库表：

```bash
python scripts/init_db.py
```

## 目录

```text
app/
  api.py              HTTP 接口
  domain.py           状态与 Pydantic 合同
  providers.py        云连接器 port、mock 实现和阿里云只读实现
  scanner.py          原生信号归因和确定性规则
  service.py          审批与白名单执行编排
  store.py            内存仓库与 SQLAlchemy Repository
  db.py               数据库表模型和会话工厂
  settings.py         环境变量配置
  static/             React 未构建时的旧静态回退页面
frontend/
  src/                React/TypeScript Console
  package.json        Vite 前端工程配置
docs/
  feasibility.md      阿里云能力与范围核验
  iam.md              最小权限角色设计
  architecture.md     工程架构与演进路线
infra/
  docker-compose.yml  本地 Compose
scripts/
  init_db.py          创建本地/远端数据库表
tests/                核心流程测试
```

## 开发前文档

正式开发前的项目基线已整理到 [docs/README.md](docs/README.md)，包括项目章程、PRD、系统架构、Agent/Playbook、数据/API、安全合规、评测、技术栈、路线图、工程规范、Demo Story、部署运行手册和阿里云原生生态定位。

## 上线边界

真实部署时，应用运行在 ECS；数据使用 RDS PostgreSQL、Tair 和 OSS；使用 RAM Role/STS 临时凭证。具体步骤见 [docs/architecture.md](docs/architecture.md) 与 [docs/iam.md](docs/iam.md)。

任何实际变更均应：先使用只读角色验证资源，再由人工批准短时写角色执行单一 Playbook，最后自动验证和记录审计事件。

当前真实执行边界：

- 默认 `SOLOOPS_EXECUTION_ENABLED=false`，所有 Playbook 只做 dry-run。
- 开启真实执行后，只允许撤销证据中精确匹配的 `ingress + tcp + 5432/5432 + 0.0.0.0/0` 安全组规则。
- 执行目标必须等于 `.env` 中的 `SOLOOPS_ALIYUN_SECURITY_GROUP_ID`。
- 磁盘诊断、容器诊断、RDS/OSS 复核类 Playbook 仍是只读采集，不会改云资源。
