---
name: pricing-profit-skill
description: Create and review travel pricing, profit, gross margin, quote structure, cost split, seat or room inventory risk, and contribution-profit analysis for Shenzhen Zhily products. Use when the task mentions pricing, quote, profit, margin, cost, GMV, contribution, break-even, inventory risk, seat, room, or package price.
---

# Pricing Profit Skill

## 触发场景

- 旅游产品报价、成本拆分、毛利测算、保本点和利润复盘。
- 判断包机、切位、包房、地接成本和渠道佣金是否可做。
- 给销售或老板输出价格调整建议。

## 执行流程

1. 收集成本项：机票、酒店、地接、车导、餐、门票、保险、签证、平台佣金、人工、税费。
2. 区分固定成本、变动成本、渠道成本和风险准备金。
3. 标记 `待核价` 成本，不用猜测填平模型。
4. 计算可确认部分的毛利、贡献利润、保本人数和敏感项。
5. 输出可执行定价建议和不建议销售的风险线。

## 禁止事项

- 不编造成本、底价、返点、返佣、库存、汇率或利润。
- 不用单一 GMV 判断产品好坏，必须看毛利、现金流和履约风险。
- 不绕开财务确认收款、退款、发票、税费和账期。
- 不把促销价当长期可持续价格。

## 完成标准

- 成本拆分完整，已确认和待确认分开。
- 利润测算公式清楚，关键敏感项可复核。
- 给出可卖、不建议卖或需补数据后再判断的结论。

## 输出格式

```markdown
## 定价利润
- 结论：
- 成本表：
- 毛利/贡献利润：
- 敏感项：
- 待核价：
```
