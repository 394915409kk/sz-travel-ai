from datetime import date

from fastapi import APIRouter

from apps.backend.services.audit_service import AuditService


router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("")
def list_audit_logs(
    module_name: str | None = None,
    operation_type: str | None = None,
    resource_type: str | None = None,
    actor: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    logs = AuditService.list_audit_logs(
        module_name=module_name,
        operation_type=operation_type,
        resource_type=resource_type,
        actor=actor,
        date_from=date_from,
        date_to=date_to,
    )
    return {"success": True, "count": len(logs), "audit_logs": logs}
