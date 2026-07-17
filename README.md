# SoloOps

> 面向独立开发者的 AI 应用运维副驾：证据化巡检、受限修复计划、人工审批和可审计执行。

SoloOps 的 MVP 默认**只读**。它从云资源、监控、部署清单和运行状态中生成 Finding；只有经过人工批准且命中受限 Playbook 的操作才允许执行。项目刻意不包含任意 SSH、任意 Shell 或自动修改云资源的能力。

## 当前实现

- FastAPI 服务与 OpenAPI 文档。
- 可离线运行的 `MockCloudProvider`：模拟 ECS、监控和安全组发现。
- 三条确定性巡检规则：公网暴露 PostgreSQL、磁盘空间不足、容器反复重启。
- Finding → Remediation Plan → Approval → Execution 的受控状态机。
- SQLAlchemy Repository：本地默认 SQLite，生产可切换 RDS PostgreSQL。
- 动作白名单与审批令牌校验；执行器当前为安全的 mock，真实阿里云执行器需单独接入。
- Docker Compose 本地环境、pytest 测试、部署/IAM/可行性文档。

## 快速开始

```bash
cp .env.example .env
docker compose up --build
```

打开 `http://localhost:8000/docs`，或运行：

```bash
curl -X POST http://localhost:8000/api/v1/scans \
  -H 'Content-Type: application/json' \
  -d '{"provider":"mock"}'
curl http://localhost:8000/api/v1/findings
```

运行本地测试：

```bash
source /Users/bytedance/my/.conda-base/etc/profile.d/conda.sh
conda activate /Users/bytedance/my/.conda-envs/soloops
pytest
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
  providers.py        云连接器 port 与 mock 实现
  scanner.py          证据采集和确定性规则
  service.py          审批与白名单执行编排
  store.py            内存仓库与 SQLAlchemy Repository
  db.py               数据库表模型和会话工厂
  settings.py         环境变量配置
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

正式开发前的项目基线已整理到 [docs/README.md](docs/README.md)，包括项目章程、PRD、系统架构、Agent/Playbook、数据/API、安全合规、评测、技术栈、路线图、工程规范、Demo Story 和部署运行手册。

## 上线边界

真实部署时，应用运行在 ECS；数据使用 RDS PostgreSQL、Tair 和 OSS；使用 RAM Role/STS 临时凭证。具体步骤见 [docs/architecture.md](docs/architecture.md) 与 [docs/iam.md](docs/iam.md)。

任何实际变更均应：先使用只读角色验证资源，再由人工批准短时写角色执行单一 Playbook，最后自动验证和记录审计事件。
