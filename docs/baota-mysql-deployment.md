# 宝塔 MySQL 部署与建表说明

本文档是 SoloOps 当前主部署数据库方案。项目持久化存储已统一切换为 MySQL。

## 1. 推荐数据库规格

宝塔演示版：

- MySQL 版本：5.7.8+ 或 8.0，当前已验证 MySQL 5.7.40。
- 字符集：`utf8mb4`。
- 排序规则：`utf8mb4_general_ci` 或 `utf8mb4_unicode_ci`。
- 存储引擎：InnoDB。
- 访问权限：
  - 本地部署时优先只允许 `localhost` 或 ECS 内网访问。
  - 本地电脑联调时可临时开放公网访问，但建议只放行自己的出口 IP。

宝塔创建：

```text
数据库名: soloops
用户名: soloops
密码: 使用强密码
访问权限: 本地服务器或指定公网 IP；临时联调可用全局
字符集: utf8mb4
```

## 2. 连接串配置

`.env` 中配置：

```env
SOLOOPS_STORE_BACKEND=sqlalchemy
SOLOOPS_DATABASE_URL=mysql+pymysql://soloops:password@host:3306/soloops?charset=utf8mb4
```

如果密码包含 `@`、`:`、`/`、`#`、`?`、`&` 等字符，需要 URL 编码。

## 3. 建表方式

项目使用 SQLAlchemy 管理表结构。你不需要手写 DDL，执行：

```bash
source /Users/bytedance/my/.conda-base/etc/profile.d/conda.sh
conda activate /Users/bytedance/my/.conda-envs/soloops
python scripts/init_db.py
```

脚本会创建以下表：

```text
scans
findings
remediation_plans
approvals
executions
audit_events
agent_runs
```

当前仍是轻量建表和轻量迁移；后续 W9 建议引入 Alembic，把表结构变更纳入正式 migration。

## 4. 最小连通性检查

端口：

```bash
nc -vz host 3306
```

SQLAlchemy：

```bash
python -c "from sqlalchemy import create_engine, text; e=create_engine('mysql+pymysql://soloops:password@host:3306/soloops?charset=utf8mb4'); c=e.connect(); print(c.execute(text('select database(), current_user(), version()')).fetchone()); c.close()"
```

## 5. 启动应用

本地：

```bash
uvicorn app.api:app --reload
```

宝塔 Python 项目管理器：

```bash
uvicorn app.api:app --host 127.0.0.1 --port 8000
```

然后在宝塔网站里配置 Nginx 反向代理到：

```text
http://127.0.0.1:8000
```

## 6. 注意事项

- 不要对远程 MySQL 直接跑会清库的测试。当前 `tests/test_api.py` 会切换到 `SOLOOPS_STORE_BACKEND=memory`，避免污染或清空远程数据库。
- 远程库 smoke test 可以跑 mock scan，它只会插入一组 scan/finding/audit 数据。
- 生产演示默认保持 `SOLOOPS_EXECUTION_ENABLED=false`。
- 宝塔面板、阿里云安全组、服务器防火墙三处都可能影响 3306 连通。
- MySQL 5.7 的 JSON 类型可用，但版本必须大于等于 5.7.8。
