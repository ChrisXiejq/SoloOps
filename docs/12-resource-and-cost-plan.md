# SoloOps 资源与成本规划

## 1. 规划原则

SoloOps 的开发顺序应先保证本地可跑，再购买最少云资源做秋招演示，最后才扩展到准生产。成本控制原则：

- 本地开发优先 Docker Compose 和 Mock Provider，尽量不产生云费用。
- 云上演示使用单 ECS + 托管最小规格数据服务。
- 写操作默认 dry run，避免误改真实云资源。
- 模型调用设置月预算和限流，优先使用高性价比模型。

## 2. 当前 Python 环境

本项目使用工作区内 conda 兼容环境：

| 项 | 路径 |
| --- | --- |
| conda CLI | `/Users/bytedance/my/.conda-base/bin/conda` |
| micromamba | `/Users/bytedance/my/.local/bin/micromamba` |
| 项目环境 | `/Users/bytedance/my/.conda-envs/soloops` |
| 环境文件 | `environment.yml` |

常用命令：

```bash
export PATH="/Users/bytedance/my/.conda-base/bin:$PATH"
conda activate /Users/bytedance/my/.conda-envs/soloops
pytest
uvicorn app.api:app --reload
```

如果换机器重建：

```bash
conda env create -f environment.yml
conda activate soloops
```

## 3. 本地开发资源

| 资源 | 是否必须 | 建议 | 成本 |
| --- | --- | --- | --- |
| Python/Conda | 必须 | Python 3.11 + conda env | 0 |
| Docker Desktop | 必须 | 本地跑 API、MySQL、Redis、MinIO | 0 |
| Node.js/npm | 必须 | React/Vite Console 开发和构建，建议 Node 20 LTS | 0 |
| MySQL | 必须 | 宝塔 MySQL、Docker MySQL 或 RDS MySQL | 0 到低 |
| Redis | 必须 | 本地容器，后续替换 Tair | 0 |
| MinIO | 可选 | 本地模拟 OSS | 0 |
| Mock Provider | 必须 | 无云账号也能演示主链路 | 0 |

本地阶段不需要购买 RDS、Tair、OSS，也不需要真实模型 Key。

## 4. 秋招演示版推荐购买/开通

目标：让项目能在公网 HTTPS 演示，并能读取少量真实阿里云资源，但成本适中。

| 资源 | 阿里云产品 | 必要性 | 建议规格 | 预算建议 |
| --- | --- | --- | --- | --- |
| 云服务器 | ECS | 必须 | 2 vCPU / 2-4 GiB，按量或轻量级包年包月 | 低到中 |
| 数据库 | 宝塔 MySQL / RDS MySQL | 推荐 | MySQL 5.7.8+ 或 8.0，开启 utf8mb4 和自动备份 | 低到中 |
| 缓存/队列 | Tair/Redis | 可选 | 先用 ECS 内 Docker Redis；准生产再买 Tair 1GB | 0 到中 |
| 对象存储 | OSS | 推荐 | 私有 Bucket，少量诊断包和导出报告 | 很低 |
| 日志服务 | SLS | 推荐 | 小规格日志 Project，短保留周期 7-15 天 | 低 |
| 运维编排 | OOS | 推荐 | 先只读模板和执行记录，后续审批后执行模板 | OOS 本身通常低，资源另计 |
| 操作审计 | ActionTrail | 推荐 | 读取云 API 变更记录，用于归因和复盘 | 低 |
| 应用监控 | ARMS | 可选 | 后续接入应用错误、链路和告警 | 视数据量 |
| 镜像仓库 | ACR | 可选 | 个人版/基础命名空间即可 | 低或 0 |
| 域名 | 阿里云域名 | 可选 | 已有域名则复用；没有可暂用 ECS IP | 低 |
| HTTPS 证书 | 数字证书管理服务 | 推荐 | 免费 DV 证书或 Let's Encrypt | 0 到低 |
| 云监控 | CloudMonitor | 必须开通 | 读取 ECS/RDS 指标 | 通常低 |
| 权限 | RAM/STS | 必须 | 读角色、写角色、部署角色 | 0 |
| 专有网络 | VPC/安全组 | 必须 | ECS/MySQL/Tair 同 VPC；生产数据库不建议开公网 | 0 |

推荐组合：

1. **最省钱演示**：ECS/宝塔 + 宝塔 MySQL + Docker Redis + OSS + SLS。适合前期录屏和面试展示。
2. **平衡推荐**：ECS + RDS MySQL + Docker Redis + OSS + SLS。数据库托管，成本可控，是秋招项目合适档位。
3. **准生产**：ECS + RDS MySQL + Tair + OSS + SLS + ACR。架构更完整，月成本更高，适合上线长期运行。

## 5. 阿里云账号内需要申请/配置的资源

### 5.1 必须配置

- VPC、交换机、安全组。
- ECS 实例，用于部署 SoloOps API/Web/Worker。
- RAM 角色：
  - `soloops-read-role`：只读读取原生信号、资源配置和执行记录。
  - `soloops-write-role`：审批后短时写动作。
  - `soloops-deploy-role`：部署拉镜像和更新服务。
- CloudMonitor API 访问权限。
- OOS 只读权限：读取模板、执行详情和执行记录。
- ActionTrail 只读权限：读取近期云 API 变更事件。
- ECS 安全组只开放 80/443；SSH 只允许你的固定 IP。

### 5.2 推荐配置

- MySQL：保存资源快照、Finding、审批、审计。
- OSS 私有 Bucket：保存诊断包、导出报告、脱敏日志引用。
- SLS Project：收集应用日志、执行日志和告警；SoloOps 只读取脱敏摘要。
- OOS：登记可被 SoloOps 调用的低风险模板。
- ACR：保存 Docker 镜像。
- HTTPS 证书和 DNS 解析。

### 5.3 可后置

- Tair/Redis：前期可用 ECS 内 Docker Redis。
- SLB/ALB：单 ECS 演示不必买，后续多实例再引入。
- ACK/Kubernetes：秋招 MVP 不建议首发。
- WAF：公开长期运行后再考虑。

## 6. 模型资源

当前默认模型底座使用阿里云百炼 Qwen；DeepSeek 和 MiniMax 可作为后续备选供应商。

| 用途 | 推荐模型 | 原因 |
| --- | --- | --- |
| 风险解释、摘要、审批说明 | 阿里云百炼 Qwen Plus | 与阿里云生态一致，适合中文运维解释和低成本调用 |
| 复杂推理、根因分析 | Qwen Max / DeepSeek Reasoner | 用在少量高价值任务，避免全量调用 |
| 多模态或语音扩展 | MiniMax | 后续如果做语音告警、会议复盘、运维助手可用 |
| 本地/测试 | MockLLM | CI 和本地开发不消耗模型额度 |

需要申请：

- 阿里云百炼 API Key。
- DeepSeek API Key 和 MiniMax API Key 可后置。
- 模型调用月预算，建议先设低额度。
- 服务端环境变量，不要写入代码或 Git：
  - `ALIBABA_CLOUD_BAILIAN_API_KEY`
  - `SOLOOPS_MODEL_PROVIDER`
  - `SOLOOPS_MODEL_NAME`
  - `DEEPSEEK_API_KEY`
  - `MINIMAX_API_KEY`
  - `MODEL_GATEWAY_PROVIDER`
  - `MODEL_BUDGET_CNY_MONTHLY`

成本控制建议：

- Finding 生成阶段不用 LLM，只用规则。
- LLM 只在用户打开详情、生成解释、生成复盘时调用。
- 相同 Finding 的解释结果缓存。
- 高成本推理模型只用于人工触发的深度诊断。
- CI、测试和 Demo 默认使用 MockLLM。

## 7. Python 与服务依赖

当前 `pyproject.toml` 已声明：

| 分类 | 包 |
| --- | --- |
| API | `fastapi`, `uvicorn[standard]`, `pydantic` |
| 测试 | `pytest`, `httpx` |
| 阿里云 | `alibabacloud-tea-openapi`, `alibabacloud-ecs20140526`, `alibabacloud-cms20190101` |

后续正式开发预计增加：

| 能力 | 建议依赖 |
| --- | --- |
| MySQL | `sqlalchemy`, `pymysql` |
| Redis/队列 | `redis`, `rq` 或 `celery` |
| 对象存储 OSS | `oss2` 或阿里云新版 SDK |
| 配置 | `pydantic-settings` |
| 日志 | `structlog` 或标准库 JSON formatter |
| OpenTelemetry | `opentelemetry-sdk`, FastAPI instrumentation |
| 模型网关 | `httpx`，自封装 DeepSeek/MiniMax client |

## 8. 建议采购顺序

1. 暂不购买云资源，先完成本地/宝塔 MySQL Repository 和 Web Console。
2. 开通阿里云百炼 API，但设置低预算，先接 MockLLM。
3. 购买或使用已有 ECS，部署 API/Web/Worker。
4. 需要托管数据库时购买 RDS MySQL 小规格，把数据库迁出 ECS/宝塔本机。
5. 开通 OSS 和 SLS，完善审计与诊断包。
6. 真实接入阿里云原生信号 Provider：CloudMonitor、ECS 健康、安全组、OOS 执行记录。
7. 用 ActionTrail 补齐最近变更归因。
8. 需要长期演示时再购买 Tair、ACR、域名和 HTTPS。

## 8.1 W8 部署与演示资源

W8 的资源目标是完成可访问 Demo，而不是搭建复杂生产平台。推荐优先级：

1. 本地安装 Node.js 20 LTS，完成 `frontend` React Console 构建。
2. 使用 Docker 多阶段构建验证 API + React Console 一体镜像。
3. 使用已有 ECS 部署镜像，先开放 8000 做调试；演示前再加 Nginx 和 HTTPS。
4. 如果要体现企业级持久化，购买或复用小规格 RDS MySQL，或使用宝塔 MySQL 做演示。
5. 如果要体现真实云原生信号，补齐 OSS Bucket、SLS Project/Logstore、RDS 实例 ID。
6. 暂缓 ACK、ALB/WAF、高规格 Tair、高规格 RDS。

详细执行清单见 [w8-deployment-and-demo-plan.md](w8-deployment-and-demo-plan.md)。

## 9. 不建议现在购买

- Kubernetes/ACK 集群。
- 高规格 RDS 或多可用区 RDS。
- 高规格 Tair。
- SLB/ALB。
- WAF。
- GPU 实例。
- 大额度模型套餐。

这些资源会增加成本，但不会显著提升秋招 MVP 的核心说服力。
