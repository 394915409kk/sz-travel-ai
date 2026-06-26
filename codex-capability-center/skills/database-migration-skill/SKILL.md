---
name: database-migration-skill
description: Plan, implement, review, and verify database migrations for Shenzhen Zhily systems, including SQLite schema changes, Alembic-style migrations, seed data, rollback notes, compatibility checks, and data-risk controls. Use when the task mentions database, migration, schema, table, column, index, seed, SQLite, Alembic, or data backfill.
---

# Database Migration Skill

## 触发场景

- 新增表、字段、索引、约束、默认值或初始化数据。
- 修改历史数据结构、字段含义、状态枚举或唯一性规则。
- 排查迁移失败、数据不一致、回滚风险。

## 执行流程

1. 识别数据库类型、迁移工具、当前 schema 和已有迁移文件。
2. 判断是否兼容旧数据、旧接口和历史报表。
3. 先写可回滚或可兼容的迁移方案，再实现迁移文件和模型更新。
4. 对数据回填使用脱敏样例或本地测试数据。
5. 运行迁移、回滚或等效检查；记录结果。
6. 输出数据风险、备份要求和人工确认项。

## 禁止事项

- 不删除生产数据，不清空表，不覆盖真实业务记录。
- 不把真实客户证件、电话、付款、合同数据写进测试种子。
- 不在未确认影响范围时修改核心订单、财务、库存字段含义。
- 不把“待核价/待确认”字段强制改成确定值。

## 完成标准

- schema 变更、模型变更和接口使用一致。
- 迁移可在本地或测试环境验证。
- 回滚、备份或兼容策略明确。
- 影响范围和人工确认项清楚。

## 输出格式

```markdown
## 数据库迁移
- 变更：
- 兼容性：
- 验证：
- 回滚/备份：
- 待确认：
```
