# Internal Beta Runbook

本手册用于 AI Travel Autonomous Revenue OS Internal Beta Ready 阶段的本地和内测运行。

## 1. 本地启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/migrate_db.py upgrade
uvicorn apps.backend.main:app --reload
```

访问 `http://127.0.0.1:8000/docs`。

## 2. Docker 启动

```bash
cp .env.example .env
docker compose up --build
```

默认服务端口为 `8000`，SQLite 数据库存放在 Docker volume `/data/travel_products.db`。
Docker 启动只运行应用，不自动执行 Alembic 迁移。production 必须先单独执行
带 `--confirm-production` 的迁移命令。

## 3. 环境变量配置

- `APP_ENV`：`development`、`staging` 或 `production`。
- `SQLITE_DB_PATH`：SQLite 数据库文件路径。
- `SQLITE_BACKUP_DIR`：备份目录，默认 `backups/`。
- `INTERNAL_API_KEY`：内测写接口 API Key。
- `PORT`：服务端口，默认 `8000`。

## 4. 设置 INTERNAL_API_KEY

development 且未配置 API Key 时允许本地免鉴权。staging/production 必须设置：

```bash
export APP_ENV=staging
export INTERNAL_API_KEY="replace-with-private-internal-key"
```

写接口请求头：

```text
X-Internal-API-Key: replace-with-private-internal-key
X-Internal-Actor: operator-name
X-Request-Id: optional-request-id
```

## 5. 初始化数据库

```bash
python scripts/migrate_db.py upgrade
```

Alembic 迁移会创建核心业务表、索引和 `alembic_version`，不会连接任何真实支付、银行、税务或外部平台。

如需本地开发示例产品数据，可在 development 环境额外执行：

```bash
python -m apps.backend.init_db
```

该命令只作为本地开发/测试辅助，不作为生产迁移方式。

## 6. 运行测试

```bash
python3 -m pytest
```

进入内测前必须全量通过。

## 7. 运行备份

```bash
python scripts/backup_sqlite.py
```

备份文件默认输出到 `backups/`，文件名包含时间戳。
备份使用 SQLite backup API，包含已提交的 WAL 数据，并在完成后执行
`PRAGMA quick_check`。

## 8. 恢复备份

```bash
python scripts/restore_sqlite.py backups/travel_products-YYYYMMDD-HHMMSS.sqlite3
```

恢复前脚本会自动备份当前数据库。
恢复输入必须是有效 SQLite 数据库并通过 `quick_check`；验证失败时不会覆盖目标库。

## 9. 查看健康检查

- `GET /system-health`
- `GET /system-health/readiness`
- `GET /system-health/security`
- `GET /system-health/backup`
- `GET /system-health/migration`

staging/production 环境中，`security_config_ok` 必须为 `true`。
production 环境中，`migration_version_ok` 必须为 `true`。

## 9.1 Alembic 迁移检查

只读检查：

```bash
python scripts/migrate_db.py check
python scripts/migrate_db.py history
python scripts/migrate_db.py heads
python scripts/migrate_db.py current
```

已有 SQLite 业务库首次接入版本管理：

```bash
python scripts/migrate_db.py stamp-existing
```

新库初始化：

```bash
python scripts/migrate_db.py upgrade
```

生产环境执行写操作必须人工确认，并显式增加 `--confirm-production`。详细规则见 `docs/DATABASE_MIGRATIONS.md`。
production 不得直接运行 `alembic upgrade/stamp` 或 `python -m alembic` 写操作，
只能使用 `scripts/migrate_db.py`。

## 10. Swagger 验收

访问 `/docs` 后，对关键写接口添加 `X-Internal-API-Key` 请求头。只读接口可直接检查，但内测环境建议由代理层统一保护。

## 11. 常见故障处理

- 写接口返回 401：检查是否缺少 `X-Internal-API-Key`。
- 写接口返回 403：检查 API Key 是否错误，或 staging/production 是否未配置 `INTERNAL_API_KEY`。
- readiness 中 `backup_directory_ok=false`：检查 `SQLITE_BACKUP_DIR` 权限。
- readiness 中出现 `database_missing`：确认数据库路径，并人工完成迁移或恢复。
- readiness 中出现 `alembic_version_missing` / `migration_not_ready`：按迁移检查清单处理。
- readiness 中出现 critical 风险：先修复库存、订单、支付或报价状态，再继续验收。

## 12. 回滚方案

1. 停止服务。
2. 找到最近一次稳定 SQLite 备份。
3. 运行 `scripts/restore_sqlite.py`。
4. 重新启动服务并检查 `/system-health/readiness`。

## 13. 内测边界

本阶段仅适合受控网络、少量内部人员、规则化业务流测试。不得对外开放为正式生产系统。

## 14. 上线前禁止事项

- 禁止提交真实密钥。
- 禁止连接真实支付、银行、税务、发票、短信、微信、邮件、OTA、航司、酒店或外部 AI API。
- 禁止把未加密备份文件提交到 Git。
- 禁止绕过人工核价对客发布报价。
