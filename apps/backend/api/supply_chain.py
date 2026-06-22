from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from apps.backend.services.supply_chain_service import SupplyChainService


router = APIRouter(prefix="/supply-chain", tags=["supply-chain"])
SuggestionStatus = Literal["pending", "accepted", "completed", "dismissed"]


class SuggestionStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: SuggestionStatus


@router.post("/analyze")
def analyze_supply_chain():
    return {"success": True, **SupplyChainService.analyze()}


@router.get("/suppliers")
def list_suppliers():
    suppliers = SupplyChainService.list_suppliers()
    return {"success": True, "count": len(suppliers), "suppliers": suppliers}


@router.get("/procurement-suggestions")
def procurement_suggestions(status: SuggestionStatus | None = None):
    suggestions = SupplyChainService.list_suggestions(status)
    return {"success": True, "count": len(suggestions), "suggestions": suggestions}


@router.patch("/procurement-suggestions/{suggestion_id}/status")
def update_procurement_suggestion(suggestion_id: int, request: SuggestionStatusUpdate):
    return {"success": True, "suggestion": SupplyChainService.update_suggestion_status(suggestion_id, request.status)}


@router.get("/stockout-risks")
def stockout_risks():
    suppliers = [item for item in SupplyChainService.list_suppliers(risks_only=True) if "STOCK_SHORTAGE_RISK" in item["risk_flags"]]
    return {"success": True, "count": len(suppliers), "risks": suppliers}


@router.get("/slow-moving-resources")
def slow_moving_resources():
    resources = SupplyChainService.slow_moving_resources()
    return {"success": True, "count": len(resources), "resources": resources}


@router.get("/suppliers/{supplier_name}")
def supplier_detail(supplier_name: str):
    suppliers = SupplyChainService.list_suppliers(supplier_name=supplier_name)
    return {"success": True, "count": len(suppliers), "suppliers": suppliers}
