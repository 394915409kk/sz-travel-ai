# API Acceptance Checklist

本清单用于 AI Travel Autonomous Revenue OS 进入内测前的人工验收。所有写接口在 staging/production 环境需携带 `X-Internal-API-Key`。

## 1. CRM 验收

- 验收目标：客户咨询可创建、查询、跟进状态可更新。
- API：`POST /inquiries`、`GET /inquiries`、`GET /inquiries/{inquiry_id}`、`PATCH /inquiries/{inquiry_id}/status`
- 操作步骤：创建一条咨询，查询列表和详情，更新为 `contacted`。
- 预期结果：咨询字段完整，状态更新成功，`mask_sensitive=true` 时手机号和姓名脱敏。
- 风险点：客户手机号、姓名不得在外部转发场景明文暴露。

## 2. 推荐评分验收

- 验收目标：系统可基于目的地、预算、人数输出规则化推荐。
- API：`POST /recommendations`、`GET /inquiries/{inquiry_id}/recommendations`
- 操作步骤：用不同预算生成推荐，检查排序和解释字段。
- 预期结果：返回推荐列表，低预算有明确风险或兜底说明。
- 风险点：不得声称真实库存、实时价格或外部平台排名。

## 3. 跟进任务验收

- 验收目标：能从待跟进咨询生成任务并更新状态。
- API：`POST /follow-up-tasks/generate`、`GET /follow-up-tasks`、`PATCH /follow-up-tasks/{task_id}/status`
- 操作步骤：准备有 `next_follow_up_at` 的咨询，生成任务并置为 `done`。
- 预期结果：任务去重生成，完成时间稳定记录。
- 风险点：重复生成不得制造多条活跃任务。

## 4. 资源中心验收

- 验收目标：交通、酒店、门票、餐饮、活动资源可创建并按库存筛选。
- API：`POST /resources/*`、`GET /resources/*`
- 操作步骤：创建各类资源，查询 `has_stock=true/false`。
- 预期结果：库存、已售、预留满足非负和不超卖约束。
- 风险点：资源价格和库存为内部样例，未接真实供应商库存。

## 5. 报价与动态定价验收

- 验收目标：报价生成只读库存，输出成本、价格、毛利和风险标记。
- API：`POST /quotes/generate`、`GET /quotes`、`GET /quotes/{quote_id}`、`GET /quotes/{quote_id}/profit-preview`
- 操作步骤：用手动资源和自动选资源分别生成报价。
- 预期结果：报价不锁库存，`mask_sensitive=true` 时客户信息脱敏。
- 风险点：报价价格仍需人工核价后对客发布。

## 6. 报价转订单验收

- 验收目标：`proposed/accepted` 报价可原子转订单并锁库存。
- API：`POST /quotes/{quote_id}/convert-to-order`
- 操作步骤：生成报价，更新状态，再转订单。
- 预期结果：生成订单、报价状态变为 `converted_to_order`、审计日志记录。
- 风险点：并发转换只能成功一次。

## 7. Mock 支付验收

- 验收目标：Mock 支付使用 `payment_event_id` 保证幂等。
- API：`POST /orders/{order_id}/mock-payment`
- 操作步骤：同一支付事件重复提交，再用不同事件提交已支付订单。
- 预期结果：不重复扣减库存，不重复改变金额，审计日志记录。
- 风险点：本系统不接真实支付。

## 8. 订单履约验收

- 验收目标：订单证件、保险、合同、提醒流程可闭环。
- API：`POST /orders/{order_id}/documents`、`POST /orders/{order_id}/insurances`、`POST /orders/{order_id}/contracts/generate`、`POST /orders/{order_id}/contracts/{contract_id}/mock-sign`、`POST /orders/{order_id}/reminders`
- 操作步骤：支付前加保险，支付后添加证件、生成并签署合同、创建提醒。
- 预期结果：已支付订单不能改金额，履约状态按规则推进。
- 风险点：证件号查询应使用脱敏参数。

## 9. 利润中心验收

- 验收目标：订单利润、汇总、高利润和风险订单可查询。
- API：`GET /profit/orders/{order_id}`、`GET /profit/summary`、`GET /profit/orders/high-profit`、`GET /profit/orders/risk`
- 操作步骤：创建已支付订单后查询利润。
- 预期结果：未支付、取消、成本缺失均有明确风险标记。
- 风险点：利润按当前资源成本计算，正式核算需成本快照。

## 10. CEO Agent 验收

- 验收目标：规则化经营日报、风险和建议可生成。
- API：`GET /ceo-agent/daily-report`、`GET /ceo-agent/risk-alerts`、`GET /ceo-agent/recommendations`
- 操作步骤：准备订单和利润数据后查询。
- 预期结果：输出只基于系统数据，不编造外部市场结论。
- 风险点：经营建议需管理者复核。

## 11. 销售成交分析验收

- 验收目标：报价可生成成交概率、风险、话术和下一步动作。
- API：`POST /sales-conversion/analyze`、`GET /sales-conversion`、`PATCH /sales-conversion/{record_id}/stage`
- 操作步骤：对报价生成分析，更新阶段。
- 预期结果：高意向和风险列表可筛选。
- 风险点：话术为规则化建议，不替代销售判断。

## 12. 内容营销验收

- 验收目标：可按平台和内容类型生成规则化内容。
- API：`POST /content-marketing/generate`、`GET /content-marketing`、`PATCH /content-marketing/{campaign_id}/status`
- 操作步骤：生成小红书笔记和短视频脚本，更新状态。
- 预期结果：内容包含风险提示，不承诺未核实价格。
- 风险点：发布前需人工核价和审核。

## 13. 客户生命周期验收

- 验收目标：可生成客户画像、识别高价值和沉睡客户、生成复购任务。
- API：`POST /customer-lifecycle/profiles/generate`、`GET /customer-lifecycle/profiles`、`POST /customer-lifecycle/repurchase-tasks/generate`
- 操作步骤：基于历史订单生成画像并查询。
- 预期结果：`mask_sensitive=true` 时客户信息脱敏。
- 风险点：画像为内部运营辅助，不可作为自动营销授权依据。

## 14. 供应链验收

- 验收目标：供应商表现、缺货风险、滞销资源和采购建议可查看。
- API：`POST /supply-chain/analyze`、`GET /supply-chain/suppliers`、`GET /supply-chain/procurement-suggestions`
- 操作步骤：创建资源与订单后运行分析。
- 预期结果：建议可更新状态，缺货和滞销可解释。
- 风险点：不接真实供应商合同或外部库存。

## 15. 财务对账验收

- 验收目标：能生成应收/应付记录、对账报告、逾期和风险提醒。
- API：`POST /finance-control/records/generate`、`PATCH /finance-control/records/{record_id}/status`、`GET /finance-control/reconciliation-report`
- 操作步骤：对订单生成财务记录，修改状态，查询报告。
- 预期结果：关键操作进入审计日志，逾期记录有风险标记。
- 风险点：不接真实银行、税务、发票。

## 16. 管理驾驶舱验收

- 验收目标：老板总览、今日数据、销售、利润、风险、行动建议可查询。
- API：`GET /dashboard/overview`、`GET /dashboard/today`、`GET /dashboard/sales`、`GET /dashboard/profit`、`GET /dashboard/risks`、`GET /dashboard/actions`
- 操作步骤：准备线索、报价、订单、财务数据后查询。
- 预期结果：汇总口径稳定，风险不被隐藏。
- 风险点：内测数据量小，不能直接代表经营真实表现。

## 17. 系统健康检查验收

- 验收目标：检查数据库、模块、安全、备份和关键风险。
- API：`GET /system-health`、`GET /system-health/readiness`、`GET /system-health/security`、`GET /system-health/backup`
- 操作步骤：在 development 和 staging 环境分别访问。
- 预期结果：staging 未配置 API Key 时 `security_config_ok=false`。
- 风险点：readiness 通过不等于正式生产合规通过。

## 18. 备份恢复验收

- 验收目标：SQLite 可本地备份，恢复前自动备份当前库。
- API/脚本：`scripts/backup_sqlite.py`、`scripts/restore_sqlite.py`
- 操作步骤：运行备份脚本，再用备份文件恢复。
- 预期结果：`backups/` 下生成时间戳备份文件，恢复前生成二次备份。
- 风险点：备份未加密，不可放入公开仓库。

## 19. 权限与安全验收

- 验收目标：staging/production 写接口需要 `X-Internal-API-Key`。
- API：任选关键写接口，如 `POST /inquiries`、`POST /orders`
- 操作步骤：分别用缺失、错误、正确 API Key 调用。
- 预期结果：缺失返回 401，错误返回 403，正确可执行。
- 风险点：API Key 不是正式用户权限系统。

## 20. 内测上线前总检查

- 验收目标：确认系统可进入受控内测。
- API/命令：`python3 -m pytest`、`GET /system-health/readiness`
- 操作步骤：运行全量测试，检查 readiness，确认备份可用。
- 预期结果：测试通过，readiness 无 critical 风险，安全边界已告知参与人员。
- 风险点：禁止接入真实支付、真实 OTA、真实航司、真实酒店和真实外部 AI API。
