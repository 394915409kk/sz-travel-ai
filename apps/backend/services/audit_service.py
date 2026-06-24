import json
from datetime import datetime
from uuid import uuid4

from apps.backend.db import get_connection


def current_time():
    return datetime.now().isoformat(timespec="seconds")


def audit_context_from_request(request):
    return {
        "actor": request.headers.get("X-Internal-Actor") or "internal-beta",
        "request_id": request.headers.get("X-Request-Id") or uuid4().hex,
    }


def serialize_log(row):
    log = dict(row)
    try:
        detail = json.loads(log.get("detail_json") or "{}")
        log["detail"] = detail if isinstance(detail, dict) else {}
    except json.JSONDecodeError:
        log["detail"] = {}
    log.pop("detail_json", None)
    return log


class AuditService:
    @staticmethod
    def record_operation(
        operation_type,
        module_name,
        resource_type=None,
        resource_id=None,
        actor=None,
        request_id=None,
        status="success",
        detail=None,
    ):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO operation_audit_logs (
                    operation_type, module_name, resource_type, resource_id,
                    actor, request_id, status, detail_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_type,
                    module_name,
                    resource_type,
                    str(resource_id) if resource_id is not None else None,
                    actor or "internal-beta",
                    request_id or uuid4().hex,
                    status,
                    json.dumps(detail or {}, ensure_ascii=False, sort_keys=True),
                    current_time(),
                ),
            )
            audit_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return audit_id
        except Exception:
            return None

    @staticmethod
    def list_audit_logs(
        module_name=None,
        operation_type=None,
        resource_type=None,
        actor=None,
        date_from=None,
        date_to=None,
    ):
        sql = "SELECT * FROM operation_audit_logs"
        conditions = []
        params = []
        for column, value in (
            ("module_name", module_name),
            ("operation_type", operation_type),
            ("resource_type", resource_type),
            ("actor", actor),
        ):
            if value:
                conditions.append(f"{column} = ?")
                params.append(value)
        if date_from is not None:
            conditions.append("date(created_at) >= date(?)")
            params.append(date_from.isoformat())
        if date_to is not None:
            conditions.append("date(created_at) <= date(?)")
            params.append(date_to.isoformat())
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY id DESC"

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        logs = [serialize_log(row) for row in cursor.fetchall()]
        conn.close()
        return logs
