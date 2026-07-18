# 部署运行手册

## 1. 部署目标

首期生产形态采用单 ECS + 托管数据服务：

- ECS：运行 Web、API、Worker、反向代理。
- RDS PostgreSQL：业务数据、审计、Trace 元数据。
- Redis/Tair：队列、锁、缓存和幂等。
- OSS：诊断包、导出报告、脱敏日志引用。
- RAM/STS：只读读取原生信号/资源配置和审批后短时写权限。
- SLS/OTel：日志、指标和告警。

## 2. 本地启动

### 2.1 API 本地启动

```bash
cp .env.example .env
docker compose up --build
```

验证：

```bash
curl http://localhost:8000/healthz
curl -X POST http://localhost:8000/api/v1/scans \
  -H 'Content-Type: application/json' \
  -d '{"provider":"mock"}'
```

运行测试：

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
```

### 2.2 React Console 本地开发

需要 Node.js 20 LTS。

```bash
cd frontend
npm install
npm run dev
```

另一个终端启动 API：

```bash
uvicorn app.api:app --reload
```

打开 `http://localhost:5173`。Vite 会把 `/api` 和 `/healthz` 代理到 `localhost:8000`。

### 2.3 React 构建产物由 FastAPI 托管

```bash
cd frontend
npm install
npm run build
cd ..
uvicorn app.api:app --reload
```

打开 `http://localhost:8000`。FastAPI 会优先服务 `frontend/dist/index.html`；如果未构建，则回退到 `app/static/index.html`。

## 3. 环境变量

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `SOLOOPS_ENV` | `local / staging / production` | `local` |
| `SOLOOPS_EXECUTION_ENABLED` | 是否允许真实执行 | `false` |
| `DATABASE_URL` | PostgreSQL 连接串 | 本地默认 |
| `REDIS_URL` | Redis 连接串 | 本地默认 |
| `OSS_BUCKET` | 诊断包 Bucket | 空 |
| `ALIYUN_REGION` | 默认地域 | 空 |
| `ALIYUN_READ_ROLE_ARN` | 只读角色 ARN | 空 |
| `ALIYUN_WRITE_ROLE_ARN` | 写角色 ARN | 空 |
| `MODEL_GATEWAY_URL` | LLM Gateway | 空 |

生产环境必须确保 `SOLOOPS_EXECUTION_ENABLED` 默认关闭，完成写角色和 Playbook 验证后再按环境开启。

## 4. 阿里云资源准备

### 4.1 网络

- 创建 VPC 和交换机。
- ECS、RDS、Tair 放在同一 VPC。
- RDS/Tair 不开公网地址。
- 安全组只开放 80/443 到反向代理；SSH 仅限个人固定 IP 或堡垒机。

### 4.2 数据服务

- RDS PostgreSQL：开启自动备份。
- Tair/Redis：仅允许 ECS 安全组访问。
- OSS：私有 Bucket，禁止公共读写。

### 4.3 RAM/STS

创建：

- `soloops-read-role`
- `soloops-write-role`
- `soloops-deploy-role`

写角色不要常驻应用；执行时通过 STS 获取短时凭证，并叠加会话策略限制资源和动作。

## 5. 部署步骤

1. 构建镜像：

```bash
docker build -t soloops-api:latest .
```

Dockerfile 会先用 `node:20-alpine` 构建 React Console，再把 `frontend/dist` 复制进 Python 运行镜像。

2. 推送到镜像仓库。
3. 在 ECS 拉取镜像。
4. 配置 `.env.production`。
5. 运行数据库迁移。
6. 启动服务：

```bash
docker compose -f infra/docker-compose.yml up -d
```

7. 检查健康状态：

```bash
curl https://<domain>/healthz
```

8. 执行 Mock 扫描验证主链路。
9. 执行只读 Provider 权限预检。
10. 配置监控和告警。

## 6. 发布检查清单

- [ ] 镜像构建成功。
- [ ] React Console 构建成功。
- [ ] 单元和集成测试通过。
- [ ] `python scripts/run_agent_eval.py` 通过。
- [ ] 数据库迁移完成。
- [ ] RDS 自动备份开启。
- [ ] Redis/Tair 私网访问。
- [ ] OSS Bucket 私有。
- [ ] 应用未保存主账号 AccessKey。
- [ ] `SOLOOPS_EXECUTION_ENABLED=false` 初始上线。
- [ ] `/healthz` 正常。
- [ ] Mock 扫描主链路正常。
- [ ] 日志无密钥。
- [ ] 告警配置完成。

## 7. 回滚方案

### 应用回滚

1. 保留上一版本镜像 tag。
2. 发布失败时切回上一版本镜像。
3. 检查数据库迁移是否兼容。
4. 验证 `/healthz` 和扫描主链路。

### 数据库回滚

- 每次迁移前创建快照或确认 RDS 备份。
- 可逆迁移提供 down 脚本。
- 不可逆迁移必须在 PR 中说明风险和恢复方式。

### Playbook 回滚

- Playbook 版本化。
- 禁用问题版本，而不是直接覆盖。
- 已审批但未执行的旧版本计划应失效。

## 8. 运维告警

至少配置：

- API 5xx 数量。
- API P95 延迟。
- Worker 任务失败率。
- 扫描失败率。
- 执行失败率。
- 数据库连接数和慢查询。
- Redis 队列积压。
- RDS 存储空间。
- ECS CPU、内存、磁盘。
- 审批后真实执行次数。

真实执行次数告警要单独配置，高风险动作出现时通知 Owner。

## 9. 故障处理

### 扫描失败

检查：

- Provider 配置。
- STS 角色是否可 Assume。
- 云 API 是否限流。
- Region 是否正确。
- Worker 是否运行。

### 执行被拒绝

检查：

- 计划是否审批。
- 审批是否过期。
- action 是否在白名单。
- `SOLOOPS_EXECUTION_ENABLED` 是否开启。
- 写角色权限是否匹配。

### Finding 不出现

检查：

- 资源是否在扫描范围。
- 规则阈值。
- Provider 返回数据。
- Rule Engine 日志。
- 去重逻辑是否合并到历史 Finding。

## 10. 备份与恢复演练

每月至少演练一次：

1. 从 RDS 备份恢复到临时实例。
2. 使用临时配置启动 SoloOps。
3. 验证审计日志和 Finding 可查询。
4. 记录恢复耗时和问题。

演示项目也应准备一个“如何恢复”的说明，这是企业级项目可信度的重要部分。
