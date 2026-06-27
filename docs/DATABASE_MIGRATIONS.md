# 数据库迁移、备份与回滚说明

本文档用于第九阶段“生产级数据库迁移 / Alembic / 数据备份与回滚机制”。

## 1. 总原则

- Alembic 是 schema 版本管理入口。
- `scripts/migrate_db.py` 是唯一生产写入型迁移入口。
- `apps/backend/init_db.py` 只保留为本地开发和测试初始化辅助，不替代生产迁移。
- 生产环境不得在应用启动时自动建表、改表或迁移。
- 生产环境不得直接执行 Alembic CLI 写操作。
- 写入型迁移只接受 `development`、`staging`、`production`；未知 `APP_ENV` 会失败关闭。
- 任何破坏性迁移必须停止，并要求人工确认。
- 不在仓库中保存真实生产数据库连接、密码、token、客户隐私、合同原件、财务凭证或供应商底价。

## 2. 当前数据库边界

当前后端业务代码仍以 SQLite 为主：

- 默认本地库：`apps/backend/travel_products.db`
- 可通过 `SQLITE_DB_PATH` 指定 SQLite 文件位置。
- Alembic `env.py` 预留 `DATABASE_URL`，未来可接 PostgreSQL 配置。
- 当前生产迁移、备份、恢复和健康检查只正式支持文件型 SQLite。
- 当前 wrapper 会拒绝非 SQLite 写入型迁移。
- PostgreSQL 正式启用前，必须先完成数据访问层、SQL 方言、连接池、备份策略和迁移脚本专项验收。

## 3. 只读检查命令

```bash
python scripts/migrate_db.py check
python scripts/migrate_db.py history
python scripts/migrate_db.py heads
python scripts/migrate_db.py current
```

`check` 会输出：

- 目标数据库路径
- 当前 Alembic head
- 是否存在数据库文件
- 是否已有业务表
- 是否已有 `alembic_version`
- 当前版本
- SQLite quick_check
- baseline 关键表和关键字段检查
- 破坏性迁移扫描结果

## 4. 新库初始化流程

适用于本地开发、测试环境或确认为空的新数据库。

```bash
export APP_ENV=development
export SQLITE_DB_PATH=/tmp/sz-travel-ai-dev.db
python scripts/migrate_db.py check
python scripts/migrate_db.py upgrade
python scripts/migrate_db.py current
```

说明：

- 新库没有可备份的旧文件，脚本会提示 `pre_migration_backup=not_required_for_new_database`。
- `upgrade` 会创建业务表和 `alembic_version`。
- baseline migration 不插入示例产品数据。

如需要本地示例数据，可在开发环境单独执行：

```bash
python -m apps.backend.init_db
```

该命令不得作为生产迁移方式。

## 5. 已有 SQLite 库接入 Alembic

适用于当前已经存在业务表、但尚无 `alembic_version` 的数据库。

标准流程：

1. 停止应用写入。
2. 人工确认 `SQLITE_DB_PATH` 指向正确数据库。
3. 执行只读检查。
4. 确认 `check` 输出 `baseline_schema_ok=True`，并人工比对现有表结构和 baseline migration。
5. 执行 `stamp-existing`，只记录版本，不重建表。
6. 执行 `current` 和系统健康检查。

命令示例：

```bash
export APP_ENV=development
export SQLITE_DB_PATH=/path/to/existing-travel-products.db
python scripts/migrate_db.py check
python scripts/migrate_db.py stamp-existing
python scripts/migrate_db.py current
```

安全规则：

- 已有业务表但没有 `alembic_version` 时，脚本会阻止直接 `upgrade`。
- 缺表、缺关键字段或 `quick_check` 失败时，脚本会阻止 `stamp-existing`。
- `stamp-existing` 会先创建 SQLite 文件备份。
- `stamp-existing` 不会复制、删除、清空或覆盖业务数据。

## 6. 生产环境流程

生产环境只允许在人工确认后执行迁移。

生产迁移前必须确认：

- 当前分支、commit 和发布窗口已确认。
- 目标数据库路径或连接串已由人工核实。
- 已完成独立备份。
- 已完成 `check/history/heads/current`。
- 已完成迁移 SQL 审查。
- 已完成回滚窗口和负责人确认。

生产写操作必须显式增加：

```bash
APP_ENV=production python scripts/migrate_db.py upgrade --confirm-production
APP_ENV=production python scripts/migrate_db.py stamp-existing --confirm-production
```

生产环境禁止直接执行：

```bash
alembic upgrade head
alembic stamp head
python -m alembic upgrade head
```

Alembic 环境层会阻止这些直接写操作。wrapper 会为单次调用生成随机内部授权，
同时写入进程内 Alembic Config；只设置内部环境变量也不能绕过保护。该内部变量
不得由人工设置、写入 `.env` 或提交到 Git。

禁止：

- 通过应用启动自动迁移生产库。
- 在仓库保存真实 `DATABASE_URL`。
- 在未备份时迁移。
- 在未人工确认时执行破坏性迁移。

## 7. 备份机制

SQLite 写操作前，`scripts/migrate_db.py` 会调用 `scripts/backup_sqlite.py`：

- `upgrade`：目标库已存在时先备份。
- `stamp-existing`：必须先备份。
- 备份目录默认使用 `SQLITE_BACKUP_DIR`，未设置时为 `backups/`。
- 备份使用 SQLite backup API，会包含已提交的 WAL 数据。
- 备份完成后必须通过 SQLite 文件头检查和 `PRAGMA quick_check`。
- 同一时间戳发生冲突时会生成唯一文件名，不覆盖已有备份。
- `backups/` 已被 Git 忽略，不应提交到仓库。

独立备份命令：

```bash
python scripts/backup_sqlite.py
```

## 8. 回滚机制

SQLite 迁移执行失败时：

- 如迁移前已有备份，脚本会自动把备份复制回目标库。
- 操作人员仍需重新执行 `check` 和 `/system-health/readiness`。
- baseline migration 禁止反向清库；如需恢复旧状态，应使用备份恢复。

手工恢复前会先验证输入是有效 SQLite 数据库并通过 `quick_check`，然后备份当前
目标库。无效备份会在覆盖前失败并保持目标库不变。

手工恢复：

```bash
python scripts/restore_sqlite.py backups/travel_products-YYYYMMDD-HHMMSS.sqlite3
python scripts/migrate_db.py check
```

PostgreSQL 未来上线前，必须引入独立的生产备份方案，例如人工确认后的 `pg_dump`、快照或云数据库备份。不得把 PostgreSQL 密码写入仓库。

## 9. 应用启动边界

- `APP_ENV=development` 或 `APP_ENV=staging`：默认允许本地辅助初始化，便于测试。
- `APP_ENV=production`：应用启动不会自动执行 `init_database()`。
- `AUTO_INIT_DB_ON_STARTUP=false`：可在非生产环境关闭启动初始化。
- Dockerfile 和 docker-compose 只启动应用，不会自动执行 `upgrade`。
- production 缺库、缺表或未迁移时，readiness 返回 `not_ready` 和原因码，不创建空库。

## 10. 验收命令

```bash
python3 -m py_compile apps/backend/db.py apps/backend/init_db.py apps/backend/main.py apps/backend/services/system_health_service.py scripts/migrate_db.py
python scripts/migrate_db.py check
python scripts/migrate_db.py history
python scripts/migrate_db.py heads
python scripts/migrate_db.py current
python3 -m pytest tests/test_database_migrations.py tests/test_pre_production_hardening.py tests/test_system_health.py
```

进入生产前还必须执行全量测试：

```bash
python3 -m pytest
```
