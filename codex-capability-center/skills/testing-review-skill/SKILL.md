---
name: testing-review-skill
description: Review code, tests, business logic, and release readiness for Shenzhen Zhily tasks. Use when the task asks for review, testing, acceptance, QA, regression check, bug risk, missing tests, or production readiness.
---

# Testing Review Skill

## 触发场景

- 用户要求 review、验收、测试覆盖、风险检查或上线前检查。
- PR 合并前需要确认代码、业务逻辑、数据迁移和安全风险。
- Bug 修复后需要验证复现路径和回归风险。

## 执行流程

1. 明确评审范围和目标：代码、API、数据库、前端、业务规则或文档。
2. 阅读差异、相关调用链、测试和验收标准。
3. 优先列出 bug、回归风险、缺失测试和数据安全问题。
4. 必要时运行最小相关测试。
5. 将发现按严重程度排序，并给出具体文件和行号。

## 禁止事项

- 不把风格建议放在严重 bug 前面。
- 不在没有证据时判断“已无风险”。
- 不忽略业务红线：价格、库存、政策、利润、客户隐私、付款权限。
- 不替代法务、财务或安全最终审批。

## 完成标准

- 发现项有文件、位置、原因和影响。
- 测试结果或未测试原因明确。
- 剩余风险和人工验收点已列出。
- 无问题时也说明检查范围和测试缺口。

## 输出格式

```markdown
## Review 发现
- [P1/P2/P3] 文件:行号 - 问题与影响

## 测试
- 已运行：
- 未覆盖：

## 结论
- 是否建议通过：
- 人工确认：
```
