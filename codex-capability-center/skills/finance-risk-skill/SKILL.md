---
name: finance-risk-skill
description: Analyze travel finance risk, cash flow, receivables, payables, refund exposure, reconciliation, budget control, and boss-facing financial warnings for Shenzhen Zhily. Use when the task mentions finance, cash flow, receivable, payable, reconciliation, refund, budget, profit report, loss, overdue, or financial risk.
---

# Finance Risk Skill

## 触发场景

- 经营日报、利润日报、现金流预警、应收应付、退款和对账。
- 分析项目是否亏损、现金流是否紧张、客户或供应商账期是否异常。
- 给老板输出财务风险和三件事行动建议。

## 执行流程

1. 区分已收、应收、已付、应付、待退、待核销、待开票。
2. 不足数据先输出补数据清单，不生成正式财务结论。
3. 检查利润、现金流、账期、退款、坏账、库存预付款和税费风险。
4. 按老板视角输出结论、表格、风险、行动项。
5. 标记需财务、业务或供应商确认的数据。

## 禁止事项

- 不编造收入、成本、利润、现金、账期、发票或退款数据。
- 不替代会计、税务、审计或法务最终判断。
- 不输出付款指令、退款承诺或银行信息。
- 不把 GMV 当作利润或现金流。

## 完成标准

- 有数据时结论可复核；无数据时只输出补数据清单。
- 风险按金额、紧急度和责任人排序。
- 行动项明确到谁补、补什么、何时补。

## 输出格式

```markdown
## 财务风险
- 先结论：
- 数据表：
- 风险项：
- 明日三件事：
- 补数据/待确认：
```
