# 生产前数据库迁移检查清单

## 1. 基础确认

- [ ] 当前分支不是 `main` 直接开发分支。
- [ ] 当前代码已完成评审。
- [ ] 当前 release 范围只包含已确认迁移。
- [ ] `.env` 未被修改或提交。
- [ ] 仓库未保存真实生产数据库连接、密码、token、客户隐私、合同原件、财务凭证、供应商底价或付款审批资料。

## 2. 目标库确认

- [ ] 人工确认 `SQLITE_DB_PATH` 或 `DATABASE_URL` 指向正确环境。
- [ ] 人工确认不是误连本地测试库、临时库或其他项目库。
- [ ] PostgreSQL 如需启用，已完成单独技术验收和备份方案确认。
- [ ] 生产连接信息只存在于受控运行环境，不写入 Git。

## 3. 迁移前备份

- [ ] SQLite 已执行 `python scripts/backup_sqlite.py` 或由迁移脚本自动生成备份。
- [ ] 备份文件已验证可读。
- [ ] 已记录备份路径。
- [ ] 已确认备份文件不会提交到 Git。
- [ ] 已确认恢复负责人和恢复窗口。

## 4. Alembic 检查

- [ ] `python scripts/migrate_db.py check` 通过。
- [ ] `python scripts/migrate_db.py history` 输出符合预期。
- [ ] `python scripts/migrate_db.py heads` 只有预期 head。
- [ ] `python scripts/migrate_db.py current` 符合当前环境状态。
- [ ] 已有库无 `alembic_version` 时，使用 `stamp-existing`，不直接 `upgrade`。
- [ ] 新库确认为空时，才允许 `upgrade` 初始化。

## 5. 破坏性迁移拦截

- [ ] 迁移文件不包含删除表。
- [ ] 迁移文件不包含删除列。
- [ ] 迁移文件不包含清空表。
- [ ] 迁移文件不包含批量删除业务数据。
- [ ] 如业务确需破坏性迁移，已停止自动执行并取得人工书面确认。

## 6. 生产执行边界

- [ ] 生产写操作已显式添加 `--confirm-production`。
- [ ] 应用启动不会自动执行生产迁移。
- [ ] 未执行自动 commit。
- [ ] 未执行自动 push。
- [ ] 未执行自动 merge。
- [ ] 未执行自动发布。

## 7. 迁移后验收

- [ ] `python scripts/migrate_db.py current` 显示目标版本。
- [ ] `/system-health/migration` 显示 `current_is_head=true`。
- [ ] `/system-health/readiness` 无数据库迁移阻断项。
- [ ] 核心 API 验收通过。
- [ ] 全量测试通过或已记录人工豁免。

## 8. 回滚准备

- [ ] 已确认最近一次稳定备份路径。
- [ ] 已验证 `scripts/restore_sqlite.py` 使用方式。
- [ ] 已确认服务停止、恢复、重启、健康检查步骤。
- [ ] 已记录迁移失败联系人和决策人。
