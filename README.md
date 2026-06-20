# sz-travel-ai

深圳市职工国际旅行社 AI 数字员工系统 v1.0

## 项目定位

当前版本是一个 FastAPI 后端 MVP，已完成最小业务闭环：

客户提出需求 -> 系统保存咨询 -> 系统匹配产品 -> 返回推荐结果 -> 销售人员跟进。

## 代码结构

```text
apps/backend/main.py                 FastAPI 应用入口
apps/backend/db.py                   SQLite 连接配置
apps/backend/init_db.py              数据库表初始化和产品种子数据
apps/backend/init_inquiries_db.py    咨询表初始化兼容入口
apps/backend/api/travel.py           旅游产品接口
apps/backend/api/inquiry.py          客户咨询接口
apps/backend/api/recommendation.py   产品推荐和 AI 策略接口
apps/backend/services/agent_team.py  多智能体策略分析服务
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
| POST | `/products/{product_id}/ai-collaborative-strategy` | 基于真实产品数据生成多智能体营销策略 |

## 推荐评分规则

产品推荐按 100 分制规则计分：目的地 40 分、预算 30 分、人数 10 分、出发日期 5 分、需求关键词 15 分。当前产品未设置人数和可售日期限制时，对应维度按中性分计算。

正常情况下不推荐严重超预算且条件不匹配的产品；如果没有合格候选，系统会返回最接近的产品，并提示销售人工确认预算或条件差异。

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
