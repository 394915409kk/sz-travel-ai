from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.backend.api.travel import router as travel_router
from apps.backend.api.inquiry import router as inquiry_router
from apps.backend.api.recommendation import router as recommendation_router
from apps.backend.api.follow_up_task import router as follow_up_task_router
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
