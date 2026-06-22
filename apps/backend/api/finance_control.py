from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

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
def generate_finance_records(request: FinanceGenerate):
    records = FinanceControlService.generate_records(request.order_id, request.receivable_due_days, request.payable_due_days)
    return {"success": True, "generated_count": len(records), "records": records}


@router.get("/records")
def list_finance_records(record_type: RecordType | None = None, direction: Direction | None = None, status: FinanceStatus | None = None):
    records = FinanceControlService.list_records(record_type, direction, status)
    return {"success": True, "count": len(records), "records": records}


@router.patch("/records/{record_id}/status")
def update_finance_record(record_id: int, request: FinanceStatusUpdate):
    return {"success": True, "record": FinanceControlService.update_status(record_id, request.status)}


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
