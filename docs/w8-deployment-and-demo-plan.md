# W8 部署与演示完成计划

W8 的目标不是继续扩规则，而是把 W1-W7 的能力变成“可部署、可演示、可复盘”的秋招展示版。

## 1. W8 退出标准

- 本地一条命令启动 API、数据库、队列依赖和 React Console。
- Docker 镜像能构建，镜像内包含 React 构建产物。
- 线上测试环境可访问 `/`、`/healthz` 和核心 API。
- Mock Demo 能稳定展示：扫描、Finding、Agent 解释、Plan、审批、执行、审计。
- Aliyun 只读 Demo 能展示真实 ECS/安全组/OOS/ActionTrail/RDS/OSS/SLS 中已配置的资源或 provider error。
- README、部署手册、演示脚本和故障排查文档同步。
- `pytest`、`python scripts/run_agent_eval.py`、前端 build 全部通过。

## 2. 需要的资源

### 2.1 本地开发资源

| 资源 | 版本/建议 | 用途 | 是否必须 |
| --- | --- | --- | --- |
| Conda 环境 | Python 3.11 | API、测试、Agent eval | 必须 |
| Docker Desktop | 最新稳定版 | 本地部署和镜像验证 | 推荐 |
| Node.js | 20 LTS | React Console 开发和构建 | 必须 |
| npm | Node 自带 | 前端依赖安装 | 必须 |
| MySQL | 宝塔 MySQL、Docker MySQL 或 RDS MySQL | 准生产验证 | 推荐 |
| Redis | Docker Compose | 后续队列替换准备 | 推荐 |

当前项目的 Conda 环境已安装 Node.js 20 和 npm；换机器重建环境时，`environment.yml` 会一并安装 Node.js。

### 2.2 阿里云演示资源

| 资源 | 建议规格 | W8 用途 | 成本建议 |
| --- | --- | --- | --- |
| ECS | 2 vCPU / 2-4 GiB | 部署 SoloOps API + React Console | 低到中 |
| MySQL | 宝塔 MySQL 或 RDS MySQL 5.7+/8.0 | 保存 scan/finding/approval/audit/agent_runs | 低到中 |
| OSS Bucket | 私有 bucket | 诊断包、报告导出，OSS 规则真实读取 | 很低 |
| SLS Project/Logstore | 7-15 天保留 | 容器重启、错误日志、发布后异常模式 | 低 |
| OOS | 只读模板/执行记录 | 展示原生运维编排治理 | 低 |
| ActionTrail | 默认开启 | 最近变更归因 | 低 |
| RAM 用户/角色 | 最小权限 | 只读读取，后续 STS 写角色 | 0 |
| 域名/HTTPS | 可选 | 面试演示链接 | 0 到低 |

W8 不建议购买 ACK、ALB、WAF、高规格 Tair 或高规格 RDS。这些会增加成本，但对当前展示价值有限。

### 2.3 必填环境变量

本地 Mock Demo 如果要持久化，至少需要：

```env
SOLOOPS_STORE_BACKEND=sqlalchemy
SOLOOPS_DATABASE_URL=mysql+pymysql://soloops:password@host:3306/soloops?charset=utf8mb4
SOLOOPS_MODEL_PROVIDER=mock
SOLOOPS_MODEL_NAME=deterministic-agent
SOLOOPS_EXECUTION_ENABLED=false
```

单元测试可使用内存仓库，不会连接数据库：

```env
SOLOOPS_STORE_BACKEND=memory
```

Qwen Agent Demo 需要：

```env
SOLOOPS_MODEL_PROVIDER=aliyun_bailian
SOLOOPS_MODEL_NAME=qwen-plus
ALIBABA_CLOUD_BAILIAN_API_KEY=
```

Aliyun 只读 Demo 需要：

```env
SOLOOPS_ALIYUN_ACCOUNT_ID=your-account-id
SOLOOPS_ALIYUN_REGION=cn-shanghai
SOLOOPS_ALIYUN_ECS_INSTANCE_ID=your-ecs-instance-id
SOLOOPS_ALIYUN_VPC_ID=your-vpc-id
SOLOOPS_ALIYUN_SECURITY_GROUP_ID=your-security-group-id
SOLOOPS_ALIYUN_RDS_INSTANCE_ID=your-rds-instance-id
SOLOOPS_ALIYUN_OSS_BUCKET=your-oss-bucket
SOLOOPS_ALIYUN_SLS_PROJECT=your-sls-project
SOLOOPS_ALIYUN_SLS_LOGSTORE=your-sls-logstore
ALIBABA_CLOUD_ACCESS_KEY_ID=your-ak
ALIBABA_CLOUD_ACCESS_KEY_SECRET=
```

生产或公开演示默认保持：

```env
SOLOOPS_EXECUTION_ENABLED=false
```

## 3. 本地部署方式

### 3.1 API + 旧静态回退

适合没有 Node 的机器：

```bash
source /Users/bytedance/my/.conda-base/etc/profile.d/conda.sh
conda activate /Users/bytedance/my/.conda-envs/soloops
pip install -e ".[dev,aliyun]"
uvicorn app.api:app --reload
```

打开：

```text
http://localhost:8000
```

如果 `frontend/dist` 不存在，FastAPI 会回退到 `app/static/index.html`。

### 3.2 React 开发模式

激活 Conda 环境后：

```bash
cd frontend
npm install
npm run dev
```

另一个终端启动 API：

```bash
uvicorn app.api:app --reload
```

打开：

```text
http://localhost:5173
```

Vite 会把 `/api` 和 `/healthz` 代理到 `localhost:8000`。

### 3.3 React 构建后由 FastAPI 托管

```bash
cd frontend
npm install
npm run build
cd ..
uvicorn app.api:app --reload
```

打开：

```text
http://localhost:8000
```

FastAPI 会优先读取 `frontend/dist/index.html`，并通过 `/assets/*` 服务 Vite 构建产物。

## 4. Docker 部署方式

当前 Dockerfile 已是多阶段构建：

1. `node:20-alpine` 构建 React。
2. `python:3.12-slim` 安装 SoloOps API。
3. 把 `frontend/dist` 复制进运行镜像。

构建：

```bash
docker build -t soloops:local .
```

运行：

```bash
docker run --rm -p 8000:8000 --env-file .env soloops:local
```

验证：

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/
```

Docker Compose：

```bash
docker compose up --build
```

## 5. ECS 部署步骤

### 5.1 准备 ECS

- 安装 Docker 和 Docker Compose 插件。
- 安全组开放 80/443；8000 仅调试阶段临时开放。
- SSH 只允许个人固定 IP 或堡垒机。
- `.env.production` 放在 ECS 本地，不提交 Git。

### 5.2 构建和发布

最简单方式是在 ECS 上构建：

```bash
git clone <repo> SoloOps
cd SoloOps
cp .env.example .env.production
docker compose up --build -d
```

更规范方式：

1. 本地或 CI 构建镜像。
2. 推送到 ACR。
3. ECS 拉取指定 tag。
4. 使用 `.env.production` 启动。

### 5.3 反向代理和 HTTPS

演示版可以先用 ECS IP + 8000；正式面试展示建议加 Nginx：

```nginx
server {
  listen 80;
  server_name soloops.example.com;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

HTTPS 可用阿里云免费证书或 Let's Encrypt。

## 6. W8 Demo 剧本

### 6.1 Mock 闭环 Demo

1. 打开 React Console。
2. 点击 `Run Mock Scan`。
3. 选择 `PostgreSQL is publicly reachable`。
4. 点击 `Explain with Agent`，展示结构化解释、影响、证据、下一步、安全 flags。
5. 点击 `Create Plan`。
6. 用 API 审批并执行：

```bash
curl -X POST http://localhost:8000/api/v1/plans/<plan_id>/approve \
  -H 'Content-Type: application/json' \
  -d '{"approver":"demo-owner","comment":"demo approval"}'

curl -X POST http://localhost:8000/api/v1/plans/<plan_id>/execute
```

7. 回到页面查看 Audit Trail。

### 6.2 Aliyun 只读 Demo

1. 补齐 `.env` 中 ECS、SG、RDS、OSS、SLS 配置。
2. 点击 `Run Aliyun Scan`。
3. 如果没有 Finding，点击 `Load Native Signals` 展示 OOS/ActionTrail/SLS 读取。
4. 如果某个云 API 权限不足，展示 `provider_error`，说明系统不会让整次扫描失败。

### 6.3 Agent 安全 Demo

运行：

```bash
python scripts/run_agent_eval.py
```

讲清楚：

- LLM 只解释 evidence，不做最终决策。
- Playbook 必须白名单。
- 未审批不能执行。
- 红队样例覆盖 prompt injection、未知动作和缺证据。

## 7. 验证清单

本地：

```bash
pytest
python scripts/run_agent_eval.py
```

激活 Conda 环境后：

```bash
cd frontend
npm install
npm run build
```

Docker：

```bash
docker build -t soloops:local .
docker run --rm -p 8000:8000 --env-file .env soloops:local
curl http://localhost:8000/healthz
```

线上：

- `/healthz` 返回 `{"status":"ok"}`。
- `/` 能打开 React Console。
- Mock scan 能生成 8 个 Finding。
- Agent explanation 能生成 trace。
- Audit Trail 有 `ScanRequested`、`ScanSucceeded`、`AgentRunCreated`、`PlanCreated`。
- `SOLOOPS_EXECUTION_ENABLED=false`。
- 日志中没有 AccessKey、APIKey。

## 8. W8 完成后的后续

- W9：Redis/RQ 或 Celery 替换进程内队列，Alembic 替换轻量迁移。
- W9：React 增加审批/执行页面，不再依赖 curl。
- W10：线上监控、备份恢复演练、录屏脚本和面试讲解稿。
