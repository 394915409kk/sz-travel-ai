from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.backend.security import require_internal_api_key
from apps.backend.services.audit_service import AuditService, audit_context_from_request
from apps.backend.services.privacy_service import PrivacyService
from apps.backend.services.quote_service import QuoteService
from apps.backend.services.quote_to_order_service import QuoteToOrderService


router = APIRouter()

QuoteStatus = Literal[
    "draft",
    "proposed",
    "accepted",
    "rejected",
    "expired",
    "converted_to_order",
]
PricingStrategy = Literal[
    "cost_plus",
    "budget_based",
    "inventory_based",
    "margin_protection",
    "mixed",
]
ResourceType = Literal[
    "transport",
    "hotel_room",
    "attraction_ticket",
    "restaurant_meal",
    "activity",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuoteResourceItem(StrictModel):
    resource_type: ResourceType
    resource_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class QuoteGenerate(StrictModel):
    inquiry_id: int | None = Field(default=None, gt=0)
    customer_name: str | None = Field(default=None, min_length=1)
    phone: str | None = None
    destination: str | None = Field(default=None, min_length=1)
    people_count: int | None = Field(default=None, gt=0)
    customer_budget: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    target_margin: float = Field(
        default=0.20,
        ge=0,
        lt=1,
        allow_inf_nan=False,
    )
    departure_date: date | None = None
    resource_items: list[QuoteResourceItem] = Field(default_factory=list)
    pricing_strategy: PricingStrategy = "mixed"

    @model_validator(mode="after")
    def validate_manual_quote(self):
        if self.inquiry_id is None:
            if not self.customer_name:
                raise ValueError("手动生成报价时 customer_name 必填")
            if not self.destination:
                raise ValueError("手动生成报价时 destination 必填")
        return self


class QuoteStatusUpdate(StrictModel):
    quote_status: QuoteStatus


@router.post("/quotes/generate")
def generate_quote(
    request: QuoteGenerate,
    _: None = Depends(require_internal_api_key),
):
    quote = QuoteService.generate(request.model_dump(mode="json"))
    return {"success": True, "quote": quote}


@router.get("/quotes")
def get_quotes(
    destination: str | None = None,
    quote_status: QuoteStatus | None = None,
    inquiry_id: int | None = Query(default=None, gt=0),
    date_from: date | None = None,
    date_to: date | None = None,
    min_margin: float | None = Query(default=None, ge=0, le=1),
    max_price: float | None = Query(default=None, ge=0),
    mask_sensitive: bool = False,
):
    quotes = QuoteService.list_quotes(
        destination=destination,
        quote_status=quote_status,
        inquiry_id=inquiry_id,
        date_from=date_from,
        date_to=date_to,
        min_margin=min_margin,
        max_price=max_price,
    )
    if mask_sensitive:
        quotes = PrivacyService.mask_sensitive_dict(quotes)
    return {"success": True, "count": len(quotes), "quotes": quotes}


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: int, mask_sensitive: bool = False):
    quote = QuoteService.get(quote_id)
    if mask_sensitive:
        quote = PrivacyService.mask_sensitive_dict(quote)
    return {"success": True, "quote": quote}


@router.patch("/quotes/{quote_id}/status")
def update_quote_status(
    quote_id: int,
    request: QuoteStatusUpdate,
    _: None = Depends(require_internal_api_key),
):
    quote = QuoteService.update_status(quote_id, request.quote_status)
    return {"success": True, "quote": quote}


@router.post("/quotes/{quote_id}/convert-to-order")
def convert_quote_to_order(
    quote_id: int,
    http_request: Request,
    _: None = Depends(require_internal_api_key),
):
    result = QuoteToOrderService.convert(quote_id)
    context = audit_context_from_request(http_request)
    AuditService.record_operation(
        operation_type="convert_quote_to_order",
        module_name="quotes",
        resource_type="quote",
        resource_id=quote_id,
        actor=context["actor"],
        request_id=context["request_id"],
        detail={
            "order_id": result["order"]["id"],
            "quote_no": result["quote"]["quote_no"],
        },
    )
    return {"success": True, **result}


@router.get("/quotes/{quote_id}/profit-preview")
def get_quote_profit_preview(quote_id: int):
    quote = QuoteService.get(quote_id)
    return {
        "quote_id": quote["id"],
        "quote_no": quote["quote_no"],
        "base_cost": quote["base_cost"],
        "final_price": quote["final_price"],
        "estimated_profit": quote["estimated_profit"],
        "estimated_margin": quote["estimated_margin"],
        "target_margin": quote["target_margin"],
        "risk_flags": quote["risk_flags"],
        "recommendation": quote["recommendation"],
    }
