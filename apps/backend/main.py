from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.backend.api.travel import router as travel_router
from apps.backend.api.inquiry import router as inquiry_router
from apps.backend.api.recommendation import router as recommendation_router
from apps.backend.api.follow_up_task import router as follow_up_task_router
from apps.backend.api.resource import router as resource_router
from apps.backend.api.order import router as order_router
from apps.backend.api.profit import router as profit_router
from apps.backend.api.quote import router as quote_router
from apps.backend.api.ceo_agent import router as ceo_agent_router
from apps.backend.api.sales_conversion import router as sales_conversion_router
from apps.backend.api.content_marketing import router as content_marketing_router
from apps.backend.api.customer_lifecycle import router as customer_lifecycle_router
from apps.backend.init_db import init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="深圳市职工国际旅行社 AI 数字员工系统",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
def read_root():
    return {
        "message": "深圳市职工国际旅行社 AI 数字员工系统",
        "status": "ok"
    }


app.include_router(travel_router)
app.include_router(inquiry_router)
app.include_router(recommendation_router)
app.include_router(follow_up_task_router)
app.include_router(resource_router)
app.include_router(order_router)
app.include_router(profit_router)
app.include_router(ceo_agent_router)
app.include_router(quote_router)
app.include_router(sales_conversion_router)
app.include_router(content_marketing_router)
app.include_router(customer_lifecycle_router)
