from fastapi import FastAPI
from apps.backend.api.travel import router as travel_router
from apps.backend.api.inquiry import router as inquiry_router
from apps.backend.api.recommendation import router as recommendation_router
app = FastAPI()
@app.get("/")
def read_root():
    return {"message": "Hello, World!"}
app.include_router(travel_router)
app.include_router(inquiry_router)
app.include_router(recommendation_router)