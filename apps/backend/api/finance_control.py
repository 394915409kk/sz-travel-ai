from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from apps.backend.security import require_internal_api_key
from apps.backend.services.audit_service import AuditService, audit_context_from_request
from apps.backend.services.finance_control_service import FinanceControlService


router = APIRouter(prefix="/finance-control", tags=["finance-control"])
RecordType = Literal["receivable", "payable", "refund", "supplier_cost", "insurance_income", "adjustment"]
Direction = Literal["income", "expense"]
FinanceStatus = Literal["pending", "paid", "overdue", "cancelled", "disputed"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FinanceGenerate(StrictModel):
    order_id: int | None = Field(default=None, gt=0)
    receivable_due_days: int = Field(default=3, ge=0, le=365)
    payable_due_days: int = Field(default=7, ge=0, le=365)


class FinanceStatusUpdate(StrictModel):
    status: FinanceStatus


@router.post("/records/generate")
def generate_finance_records(
    request: FinanceGenerate,
    http_request: Request,
    _: None = Depends(require_internal_api_key),
):
    records = FinanceControlService.generate_records(request.order_id, request.receivable_due_days, request.payable_due_days)
    context = audit_context_from_request(http_request)
    AuditService.record_operation(
        operation_type="generate_finance_records",
        module_name="finance_control",
        resource_type="order",
        resource_id=request.order_id,
        actor=context["actor"],
        request_id=context["request_id"],
        detail={
            "generated_count": len(records),
            "receivable_due_days": request.receivable_due_days,
            "payable_due_days": request.payable_due_days,
        },
    )
    return {"success": True, "generated_count": len(records), "records": records}


@router.get("/records")
def list_finance_records(record_type: RecordType | None = None, direction: Direction | None = None, status: FinanceStatus | None = None):
    records = FinanceControlService.list_records(record_type, direction, status)
    return {"success": True, "count": len(records), "records": records}


@router.patch("/records/{record_id}/status")
def update_finance_record(
    record_id: int,
    request: FinanceStatusUpdate,
    http_request: Request,
    _: None = Depends(require_internal_api_key),
):
    record = FinanceControlService.update_status(record_id, request.status)
    context = audit_context_from_request(http_request)
    AuditService.record_operation(
        operation_type="update_finance_record_status",
        module_name="finance_control",
        resource_type="finance_record",
        resource_id=record_id,
        actor=context["actor"],
        request_id=context["request_id"],
        detail={"status": request.status, "order_id": record["order_id"]},
    )
    return {"success": True, "record": record}


@router.get("/reconciliation-report")
def reconciliation_report(report_date: date | None = None):
    return {"success": True, "report": FinanceControlService.reconciliation_report(report_date)}


@router.get("/overdue")
def overdue_records():
    records = FinanceControlService.list_records(status="overdue")
    return {"success": True, "count": len(records), "records": records}


@router.get("/risk-alerts")
def finance_risk_alerts():
    alerts = FinanceControlService.risk_alerts()
    return {"success": True, "count": len(alerts), "alerts": alerts}
