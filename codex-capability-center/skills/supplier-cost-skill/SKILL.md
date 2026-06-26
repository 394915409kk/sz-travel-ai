---
name: supplier-cost-skill
description: Manage supplier cost analysis, negotiation preparation, settlement terms, resource comparison, and supplier-risk controls for Shenzhen Zhily travel operations. Use when the task mentions supplier, airline, hotel, DMC, ground operator, cost, settlement, allotment, negotiation, payment term, or resource comparison.
---

# Supplier Cost Skill

## 触发场景

- 比较供应商报价、资源、账期、取消政策和履约能力。
- 准备机票、酒店、地接、车导、景区、保险、签证等谈判。
- 分析供应商成本上涨、赔付、投诉或履约失败。

## 执行流程

1. 收集供应商名称、资源类型、报价口径、有效期、包含项和取消规则。
2. 区分公开报价、合作价、底价、返点和账期，敏感信息单独标记。
3. 对比价格、履约、结算、风险、售后和替代资源。
4. 准备谈判目标、底线、让步空间和待法务/财务确认项。
5. 输出可用于内部决策的供应商对比和谈判清单。

## 禁止事项

- 不代替公司确认付款、预付款、定金、合同盖章或资源锁定。
- 不泄露供应商底价、返点、账期给不应知悉人员。
- 不编造供应商承诺、库存、房态、座位或赔付条款。
- 不把口头承诺当正式合同条款。

## 完成标准

- 供应商对比维度完整。
- 报价有效期、取消规则和结算风险清楚。
- 谈判目标和需人工确认事项明确。

## 输出格式

```markdown
## 供应商分析
- 供应商：
- 报价与口径：
- 优劣势：
- 谈判目标：
- 风险与待确认：
```
