from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from apps.backend.security import require_internal_api_key
from apps.backend.services.sales_conversion_service import SalesConversionService


router = APIRouter(prefix="/sales-conversion", tags=["sales-conversion"])
ConversionStage = Literal[
    "new", "quoted", "negotiating", "high_intent", "low_intent",
    "accepted", "lost", "converted",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SalesConversionAnalyze(StrictModel):
    quote_id: int = Field(gt=0)
    customer_objections: list[str] = Field(default_factory=list)


class SalesConversionStageUpdate(StrictModel):
    conversion_stage: ConversionStage


@router.post("/analyze")
def analyze_sales_conversion(
    request: SalesConversionAnalyze,
    _: None = Depends(require_internal_api_key),
):
    return {"success": True, "record": SalesConversionService.analyze(request.quote_id, request.customer_objections)}


@router.get("")
def list_sales_conversions(conversion_stage: ConversionStage | None = None):
    records = SalesConversionService.list_records(stage=conversion_stage)
    return {"success": True, "count": len(records), "records": records}


@router.get("/high-intent")
def list_high_intent_sales_conversions():
    records = SalesConversionService.list_records(high_intent=True)
    return {"success": True, "count": len(records), "records": records}


@router.get("/risk")
def list_risky_sales_conversions():
    records = SalesConversionService.list_records(risky=True)
    return {"success": True, "count": len(records), "records": records}


@router.get("/{record_id}")
def get_sales_conversion(record_id: int):
    return {"success": True, "record": SalesConversionService.get(record_id)}


@router.patch("/{record_id}/stage")
def update_sales_conversion_stage(
    record_id: int,
    request: SalesConversionStageUpdate,
    _: None = Depends(require_internal_api_key),
):
    return {"success": True, "record": SalesConversionService.update_stage(record_id, request.conversion_stage)}


@router.get("/{record_id}/follow-up-script")
def get_follow_up_script(record_id: int):
    record = SalesConversionService.get(record_id)
    return {"record_id": record_id, "follow_up_script": record["follow_up_script"], "next_best_action": record["next_best_action"]}
