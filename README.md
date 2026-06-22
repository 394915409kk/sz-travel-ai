# sz-travel-ai

深圳市职工国际旅行社 AI 数字员工系统 v1.0

## 项目定位

当前版本是一个 FastAPI 后端 MVP，已完成最小业务闭环：

客户提出需求 -> 系统保存咨询 -> 系统匹配产品/资源 -> 自动报价与动态定价 -> 销售确认 -> 报价转订单 -> 资源履约。

## 代码结构

```text
apps/backend/main.py                 FastAPI 应用入口
apps/backend/db.py                   SQLite 连接配置
apps/backend/init_db.py              数据库表初始化和产品种子数据
apps/backend/init_inquiries_db.py    咨询表初始化兼容入口
apps/backend/api/travel.py           旅游产品接口
apps/backend/api/inquiry.py          客户咨询接口
apps/backend/api/recommendation.py   产品推荐和 AI 策略接口
apps/backend/api/follow_up_task.py   销售跟进任务接口
apps/backend/api/resource.py         旅游资源与成本中心接口
apps/backend/api/order.py            订单交易与履约中心接口
apps/backend/api/profit.py           订单利润中心接口
apps/backend/api/ceo_agent.py        CEO Agent 经营分析接口
apps/backend/api/quote.py            自动报价与动态定价中心接口
apps/backend/services/agent_team.py  多智能体策略分析服务
apps/backend/services/recommendation_scoring.py  产品推荐规则评分服务
apps/backend/services/inventory_service.py  库存一致性服务
apps/backend/services/order_state_machine.py  订单状态机
apps/backend/services/payment_guard.py  支付事件幂等控制
apps/backend/services/profit_service.py  订单利润实时计算服务
apps/backend/services/ceo_agent_service.py  规则化经营分析服务
apps/backend/services/pricing_service.py  规则化动态定价服务
apps/backend/services/quote_service.py  报价生成、查询与状态服务
apps/backend/services/quote_to_order_service.py  报价转订单事务服务
tests/                               自动化测试
```

## 环境要求

- Python 3.11+
- SQLite

## 本地启动

1. 创建虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 初始化数据库：

```bash
python -m apps.backend.init_db
```

4. 启动服务：

```bash
uvicorn apps.backend.main:app --reload
```

5. 打开接口文档：

```text
http://127.0.0.1:8000/docs
```

## 环境变量

可参考 `.env.example`：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_ENV` | `development` | 运行环境标识 |
| `SQLITE_DB_PATH` | `apps/backend/travel_products.db` | SQLite 数据库文件路径，支持绝对路径或相对仓库根目录路径 |

## Docker 启动

```bash
docker compose up
```

服务启动后访问：

```text
http://127.0.0.1:8000/docs
```

## 已实现接口

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/` | 服务根路径 |
| GET | `/products` | 查询产品列表，支持目的地、品类、最高价筛选 |
| GET | `/products/{product_id}` | 查询产品详情 |
| POST | `/inquiries` | 创建客户咨询 |
| GET | `/inquiries` | 查询客户咨询列表，支持跟进状态、销售、优先级、来源、下次跟进时间筛选 |
| GET | `/inquiries/follow-up/today` | 查询今天及以前需要跟进的客户咨询 |
| GET | `/inquiries/{inquiry_id}` | 查询咨询详情 |
| PATCH | `/inquiries/{inquiry_id}/status` | 更新销售跟进状态 |
| POST | `/recommendations` | 根据客户需求生成规则评分推荐 |
| GET | `/inquiries/{inquiry_id}/recommendations` | 根据某条咨询生成规则评分推荐 |
| POST | `/follow-up-tasks/generate` | 根据已有咨询生成销售跟进任务 |
| GET | `/follow-up-tasks` | 查询任务，支持销售、状态、优先级和到期时间筛选 |
| GET | `/follow-up-tasks/today` | 查询今天及以前到期的 pending 任务 |
| GET | `/follow-up-tasks/{task_id}` | 查询单个销售跟进任务 |
| PATCH | `/follow-up-tasks/{task_id}/status` | 更新任务状态并记录完成时间 |
| POST | `/resources/transport` | 创建交通资源 |
| GET | `/resources/transport` | 查询交通资源 |
| POST | `/resources/hotel-rooms` | 创建酒店房型资源 |
| GET | `/resources/hotel-rooms` | 查询酒店房型资源 |
| POST | `/resources/attraction-tickets` | 创建景点门票资源 |
| GET | `/resources/attraction-tickets` | 查询景点门票资源 |
| POST | `/resources/restaurant-meals` | 创建餐饮资源 |
| GET | `/resources/restaurant-meals` | 查询餐饮资源 |
| POST | `/resources/activities` | 创建玩乐项目资源 |
| GET | `/resources/activities` | 查询玩乐项目资源 |
| POST | `/orders` | 手动或基于咨询创建订单，并原子锁定资源库存 |
| GET | `/orders` | 查询订单列表 |
| GET | `/orders/{order_id}` | 查询订单及资源明细 |
| PATCH | `/orders/{order_id}/status` | 更新订单状态 |
| POST | `/orders/{order_id}/mock-payment` | 模拟支付并将预留库存转为已售 |
| POST | `/orders/{order_id}/documents` | 记录订单证件资料 |
| GET | `/orders/{order_id}/documents` | 查询订单证件资料 |
| POST | `/insurance-products` | 创建保险产品 |
| GET | `/insurance-products` | 查询保险产品 |
| POST | `/orders/{order_id}/insurances` | 为订单选择保险 |
| GET | `/orders/{order_id}/insurances` | 查询订单保险 |
| POST | `/orders/{order_id}/contracts/generate` | 生成本地合同记录 |
| GET | `/orders/{order_id}/contracts` | 查询订单合同 |
| POST | `/orders/{order_id}/contracts/{contract_id}/mock-sign` | 模拟签署合同 |
| POST | `/orders/{order_id}/reminders` | 创建订单提醒 |
| GET | `/orders/{order_id}/reminders` | 查询订单提醒 |
| PATCH | `/orders/{order_id}/reminders/{reminder_id}/status` | 更新提醒状态 |
| POST | `/quotes/generate` | 按咨询或手动客户信息生成报价方案与报价明细 |
| GET | `/quotes` | 查询报价列表，支持目的地、状态、咨询、日期、毛利率和价格筛选 |
| GET | `/quotes/{quote_id}` | 查询单个报价及报价明细 |
| PATCH | `/quotes/{quote_id}/status` | 更新报价状态 |
| GET | `/quotes/{quote_id}/profit-preview` | 查询报价利润预估和风险提示 |
| POST | `/quotes/{quote_id}/convert-to-order` | 将 proposed 或 accepted 报价原子转换为订单并锁定库存 |
| GET | `/profit/orders/{order_id}` | 计算单个订单收入、资源成本、保险收入、毛利和毛利率 |
| GET | `/profit/summary` | 汇总订单利润，支持目的地、日期、销售及订单/支付状态筛选 |
| GET | `/profit/orders/high-profit` | 查询高利润订单 |
| GET | `/profit/orders/risk` | 查询低利润、亏损、未支付、取消或成本缺失订单 |
| GET | `/ceo-agent/daily-report` | 生成规则化 CEO 每日经营日报 |
| GET | `/ceo-agent/risk-alerts` | 生成订单利润与经营集中度风险预警 |
| GET | `/ceo-agent/recommendations` | 生成规则化经营建议 |
| POST | `/products/{product_id}/ai-collaborative-strategy` | 基于真实产品数据生成多智能体营销策略 |

## 推荐评分规则

产品推荐按 100 分制规则计分：目的地 40 分、预算 30 分、人数 10 分、出发日期 5 分、需求关键词 15 分。当前产品未设置人数和可售日期限制时，对应维度按中性分计算。

正常情况下不推荐严重超预算且条件不匹配的产品；如果没有合格候选，系统会返回最接近的产品，并提示销售人工确认预算或条件差异。

## 销售跟进任务模块

`follow_up_tasks` 根据咨询的 `assigned_sales`、`priority` 和 `next_follow_up_at` 生成销售待办。同一咨询已有 `pending` 或 `done` 任务时不重复生成；任务状态更新为 `done` 时自动写入 `completed_at`。

## 旅游资源与成本中心

资源中心统一管理目的地、资源名称、供应商、成本价、建议销售价、币种、可售日历、库存和状态。当前包含以下数据表：

| 数据表 | 资源类型 | 特有字段 |
|---|---|---|
| `travel_transport_resources` | 交通 | 交通类型、出发城市、到达城市 |
| `hotel_room_resources` | 酒店房型 | 酒店、房型、早餐、最大入住人数 |
| `attraction_ticket_resources` | 景点门票 | 通用资源与价格字段 |
| `restaurant_meal_resources` | 餐饮 | 餐别、人均价格 |
| `activity_resources` | 玩乐项目 | 项目类型、时长、适合人群 |

所有资源表包含以下库存字段：

- `stock_quantity`：总库存，默认为 0。
- `sold_quantity`：已售数量，默认为 0。
- `reserved_quantity`：预留数量，默认为 0。
- `available_quantity`：接口动态计算，等于总库存减已售和预留数量。

`available_dates` 在 SQLite 中保存为 JSON 日期数组。使用 `available_on` 查询时，如果资源存在非空的 `available_dates`，只按日历数组判断；日历为空时才使用 `available_start_date` 和 `available_end_date` 区间。

所有查询接口支持 `destination`、`status`、`supplier_name`、`max_cost_price`、`available_on` 和 `has_stock` 筛选。`has_stock=true` 只返回可用库存大于 0 的资源；`has_stock=false` 只返回可用库存小于或等于 0 的资源；不传该参数时返回全部库存状态。

## 订单交易与履约中心

`orders` 保存订单客户、金额、支付状态和履约状态；`order_items` 保存订单引用的交通、酒店、门票、餐饮和玩乐资源、数量与销售价快照。订单可手动创建，也可通过 `inquiry_id` 继承咨询客户信息。

创建订单时会在同一个 SQLite 事务中校验 `stock_quantity - sold_quantity - reserved_quantity` 并增加预留数量。模拟支付把订单预留库存转为已售，重复支付不会再次扣减；未支付订单取消时释放预留。证件、保险、合同和提醒均仅保存本地记录，不调用 OCR、电子签、支付或通知服务。

## 金融级一致性保障设计

- **库存锁定机制**：`InventoryConsistencyService` 是库存字段的唯一写入口。创建订单调用 `lock_stock()` 增加预留，未支付取消调用 `release_stock()` 释放预留，模拟支付调用 `commit_sale()` 将预留原子转换为已售。
- **幂等支付机制**：每次模拟支付必须提交唯一 `payment_event_id`。`PaymentIdempotencyGuard` 通过 `payment_events` 唯一约束记录处理结果；同一事件重复或并发到达时直接返回首次结果，不重复提交库存。
- **状态机控制**：`OrderStateMachine` 是 `order_status` 的唯一更新入口，只允许 `draft → pending_payment → paid → fulfilling → completed`，并允许未支付订单从 `draft` 或 `pending_payment` 取消。已支付订单拒绝取消。
- **防超卖设计**：订单创建、支付、取消和保险金额变更均使用 `BEGIN IMMEDIATE` 事务；库存锁定同时使用带可用库存条件的原子 `UPDATE`，并由数据库约束保证 `sold_quantity + reserved_quantity <= stock_quantity`。
- **防错账设计**：支付、库存转换和订单状态在同一事务中提交或回滚；支付后禁止保险修改 `total_amount`；合同操作不触碰金额和库存。SQLite 适用于当前单实例 MVP，多实例部署前仍需迁移到支持行级锁的生产数据库。

## 第七优先级：利润中心 + CEO Agent MVP

利润中心直接基于 `orders`、`order_items`、各资源表和 `order_insurances` 实时计算，不新增重复的利润快照表。当前能力包括：

- 单订单利润计算：订单收入、资源成本、保险收入、毛利和毛利率。
- 毛利率分析与利润分级：`high_profit`、`normal_profit`、`low_profit`、`loss`。
- 利润汇总：支持目的地、日期、销售、订单状态和支付状态筛选。
- 高利润订单识别：毛利率不低于 30%，或毛利不低于 1000 元。
- 风险订单识别：覆盖负毛利、低毛利、成本缺失、未支付和已取消订单。
- CEO Agent 每日经营日报：汇总收入、利润、订单、目的地、风险和高利润订单。
- CEO Agent 风险预警：覆盖低毛利、负毛利、未支付、取消、成本缺失和目的地集中风险。
- CEO Agent 经营建议：按规则提出调价、产品推广、成本补齐、催付、毛利控制和保险附加销售建议。

利润口径：`order_revenue = orders.total_amount`，保险收入包含在订单总额中并单独披露；`resource_cost` 按订单资源数量乘以资源表当前 `cost_price` 计算；`gross_profit = order_revenue - resource_cost`。订单收入为 0 时毛利率返回 `0.0`，不会执行除零运算。无订单资源明细、资源记录丢失或成本值缺失时标记 `missing_resource_cost`，提醒人工补齐后再确认利润。

本阶段不包含真实 AI 模型调用、真实财务系统、税务、发票、银行系统、外部 API 和前端页面。所有 CEO Agent 内容均由本地规则生成，不能替代正式财务核算和管理决策复核。

## 第八优先级：自动报价与动态定价中心 MVP

报价中心把客户咨询、资源成本、目标毛利和订单库存一致性连接成后端闭环。`quotes` 保存报价方案和利润预估，`quote_items` 保存资源、数量、成本和报价快照。报价可从 `inquiry_id` 继承客户、目的地、预算和出发日期，也可使用手动客户信息生成；未指定资源时，系统按目的地从当前在售且库存充足的资源中自动选择 MVP 组合。

当前规则化能力包括：

- 自动报价生成与报价明细计算。
- 按目标毛利率计算最低保护售价，资源建议售价不足时执行毛利保护。
- 可用库存不高于 2 时加价 10%，不高于 5 时加价 5%。
- 出发日期距当前日期不超过 7 天时加价 8%，不超过 14 天时加价 4%。
- 客户预算达到基础报价 120% 时识别高利润机会，最多上调基础报价的 5%，且不超过客户预算。
- 报价超过预算时不强行降到亏损价，输出销售沟通或调整资源方案建议。
- 输出基础成本、最终报价、预计利润、预计毛利率、风险标记和报价建议。
- 支持报价列表/详情查询、状态更新、利润预估和报价转订单。

报价生成只读取资源库存，不预留或扣减库存。只有 `proposed` 或 `accepted` 报价可以转订单；`rejected`、`expired` 和已转订单报价不能转换。转订单在单个 SQLite `BEGIN IMMEDIATE` 事务中创建订单，并逐项调用 `InventoryConsistencyService.lock_stock()` 锁定库存；任一资源库存不足时，订单、库存和报价状态整体回滚。同一报价只能转换一次，成功后状态更新为 `converted_to_order`，订单金额固定使用报价 `final_price`。

本阶段不包含真实 AI 模型调用、前端页面、真实 OTA、真实航司/酒店接口、真实财务系统、税务、发票、银行系统和外部 API。动态定价全部由本地可审计规则完成，正式对客前仍需销售人工复核资源、价格和库存。

## 示例请求

创建客户咨询：

```bash
curl -X POST http://127.0.0.1:8000/inquiries \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "张三",
    "phone": "13800000000",
    "destination": "北京",
    "people_count": 2,
    "budget": 5000,
    "departure_date": "2026-07-01",
    "message": "想咨询北京5日游",
    "source": "小红书",
    "assigned_sales": "王销售",
    "priority": "high",
    "next_follow_up_at": "2026-07-02T10:00:00"
  }'
```

查询需要跟进的咨询：

```bash
curl "http://127.0.0.1:8000/inquiries?assigned_sales=王销售&priority=high&source=小红书&next_follow_up_before=2026-07-02T18:00:00"
```

查询今天及以前需要跟进的咨询：

```bash
curl http://127.0.0.1:8000/inquiries/follow-up/today
```

直接获取规则评分推荐：

```bash
curl -X POST http://127.0.0.1:8000/recommendations \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "泰国",
    "people_count": 12,
    "budget": 5200,
    "departure_date": "2026-08-01",
    "message": "公司团建，希望品质好一些"
  }'
```

基于咨询获取推荐：

```bash
curl http://127.0.0.1:8000/inquiries/1/recommendations
```

根据咨询生成销售跟进任务：

```bash
curl -X POST http://127.0.0.1:8000/follow-up-tasks/generate
```

查询某位销售的高优先级待办：

```bash
curl "http://127.0.0.1:8000/follow-up-tasks?assigned_sales=王销售&task_status=pending&priority=high"
```

查询今天及以前需要处理的任务：

```bash
curl http://127.0.0.1:8000/follow-up-tasks/today
```

完成销售跟进任务：

```bash
curl -X PATCH http://127.0.0.1:8000/follow-up-tasks/1/status \
  -H "Content-Type: application/json" \
  -d '{"task_status": "done"}'
```

创建交通资源：

```bash
curl -X POST http://127.0.0.1:8000/resources/transport \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "泰国",
    "resource_name": "深圳往返曼谷机票",
    "supplier_name": "测试航空供应商",
    "transport_type": "flight",
    "departure_city": "深圳",
    "arrival_city": "曼谷",
    "cost_price": 1800,
    "sale_price": 2200,
    "stock_quantity": 10,
    "sold_quantity": 2,
    "reserved_quantity": 3,
    "available_start_date": "2026-07-01",
    "available_end_date": "2026-08-31",
    "available_dates": ["2026-07-01", "2026-07-02"]
  }'
```

查询指定日期可用、有库存且成本不高于 2000 元的泰国交通资源：

```bash
curl "http://127.0.0.1:8000/resources/transport?destination=泰国&status=active&max_cost_price=2000&available_on=2026-07-01&has_stock=true"
```

查询无可用库存的酒店房型：

```bash
curl "http://127.0.0.1:8000/resources/hotel-rooms?has_stock=false"
```

手动创建订单并锁定资源库存：

```bash
curl -X POST http://127.0.0.1:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "测试客户",
    "phone": "13800000000",
    "destination": "泰国",
    "people_count": 2,
    "items": [
      {"resource_type": "transport", "resource_id": 1, "quantity": 2}
    ]
  }'
```

执行模拟支付：

```bash
curl -X POST http://127.0.0.1:8000/orders/1/mock-payment \
  -H "Content-Type: application/json" \
  -d '{"payment_event_id": "PAY-20260621-0001"}'
```

更新销售跟进状态：

```bash
curl -X PATCH http://127.0.0.1:8000/inquiries/1/status \
  -H "Content-Type: application/json" \
  -d '{"follow_status": "contacted"}'
```

## 运行测试

```bash
pytest
```

## 当前注意事项

- 当前产品数据是初始化脚本内置的演示数据，不代表实时价格、库存或政策。
- 对外报价、库存、航班、签证政策、退款规则仍需人工复核。
- 客户手机号等敏感信息后续需要接入权限控制和脱敏展示。
- 任务生成当前由 `POST /follow-up-tasks/generate` 触发，尚未接入定时调度或外部消息通知。
- 任务时间按 SQLite 中保存的本地 ISO 日期时间比较，正式多时区部署前需要统一时区策略。
- 资源成本价和建议销售价是静态基础数据；利润中心按当前资源成本实时估算，不执行历史成本快照、动态打包、自动报价或供应商结算。
- `available_dates`、`available_start_date` 和 `available_end_date` 仅表示静态可售日历，库存数量也是内部基础数据，不代表供应商实时确认。
- 币种默认为 `CNY`，当前不包含汇率换算。
- 订单明细保存创建当时的销售价快照，后续资源调价不会自动改写已有订单。
- 订单资源成本当前未保存历史快照，资源成本价变化会影响历史订单的实时利润结果；正式财务核算前需引入成本快照或结算成本。
- `mock-payment` 和 `mock-sign` 仅用于内部流程测试；当前不包含真实支付、退款、OCR、电子签、短信、邮件、微信通知、发票、供应商结算或外部库存锁定。
