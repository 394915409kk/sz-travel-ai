---
name: backend-api-skill
description: Build, modify, review, and debug backend API work for Shenzhen Zhily travel systems, especially FastAPI routes, service layers, schemas, SQLite persistence, request validation, and API acceptance checks. Use when the task mentions backend, API, FastAPI, route, endpoint, service, schema, validation, or server-side bugfix.
---

# Backend API Skill

## 触发场景

- 新增或修改后端接口、路由、服务层、数据模型、请求校验。
- 修复接口报错、字段缺失、状态码异常、权限或幂等问题。
- 为报价、订单、产品、客户、财务、供应商等模块补齐 API 闭环。

## 执行流程

1. 确认仓库根目录、当前分支、相关路由、模型、测试和现有命名风格。
2. 先读现有实现，再设计最小改动方案；不要绕开既有服务层和校验逻辑。
3. 明确请求字段、响应字段、错误码、权限边界和数据落库行为。
4. 修改代码后补充或更新针对性测试。
5. 运行相关测试；无法运行时记录原因和替代检查。
6. 输出改动范围、验证结果、剩余风险。

## 禁止事项

- 不连接生产数据库，不写入真实客户隐私或真实付款数据。
- 不为满足接口演示而编造价格、库存、利润、政策或供应商承诺。
- 不绕过认证、授权、审计、幂等或库存锁定规则。
- 不扩大成全新业务系统或跨模块重构，除非用户明确要求。

## 完成标准

- 接口行为、字段、状态码和错误信息清楚。
- 相关测试通过，或未运行原因明确。
- 没有破坏现有兼容性和已知业务约束。
- 需要人工补数或验价的字段已标记。

## 输出格式

```markdown
## 后端改动
- 文件：
- 行为：
- 验证：
- 风险：
- 待确认：
```
