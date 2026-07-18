# W7 前遗留待办

以下事项不阻塞 W7 Agent 能力实现，但需要在 W8-W10 或上线前继续补齐。

## 云资源配置

- `.env` 仍需补真实 `SOLOOPS_ALIYUN_RDS_INSTANCE_ID`，否则 RDS 只能按地域尝试 list，无法按最小权限锁定实例。
- `.env` 仍需补真实 `SOLOOPS_ALIYUN_OSS_BUCKET`，否则 OSS 只能尝试账号级 list，生产权限面较大。
- `.env` 仍需补真实 `SOLOOPS_ALIYUN_SLS_PROJECT` 和 `SOLOOPS_ALIYUN_SLS_LOGSTORE`，否则 SLS 日志模式不会参与真实扫描。

## 生产化基础设施

- `InProcessScanQueue` 仍需替换为 Redis + RQ/Celery 或云消息队列。
- 数据库迁移仍是轻量 `ALTER TABLE`，需要引入 Alembic。
- Web Console 仍是静态 HTML，后续可迁移到 React/TypeScript。
- Provider 权限预检需要独立 API 和页面展示，而不是只依赖 scan 时的 `provider_error`。

## 受控执行

- 真实写动作目前只允许撤销精确匹配的公网 PostgreSQL 安全组规则。
- OOS 模板 Adapter 和 STS 短时写角色还需要继续接入。
- RDS/OSS 相关 Playbook 当前只做只读 review，不做自动修改。
