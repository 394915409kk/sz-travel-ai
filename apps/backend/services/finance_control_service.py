import json
from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import HTTPException

from apps.backend.db import get_connection
from apps.backend.services.inventory_service import RESOURCE_TABLES
from apps.backend.services.profit_service import ProfitService


def _json_list(value):
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def serialize_record(row):
    record = dict(row)
    record["risk_flags"] = _json_list(record.pop("risk_flags_json"))
    return record


def serialize_report(row):
    report = dict(row)
    report["risk_flags"] = _json_list(report.pop("risk_flags_json"))
    return report


class FinanceControlService:
    """内部应收应付与对账 MVP；不连接银行、税务或发票。"""

    @classmethod
    def generate_records(cls, order_id=None, receivable_due_days=3, payable_due_days=7):
        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        sql = "SELECT * FROM orders"
        params = []
        if order_id is not None:
            sql += " WHERE id = ?"
            params.append(order_id)
        sql += " ORDER BY id"
        cursor.execute(sql, params)
        orders = cursor.fetchall()
        if order_id is not None and not orders:
            conn.close()
            raise HTTPException(status_code=404, detail="未找到该订单")
        generated_ids = []
        today = date.today()
        for order in orders:
            paid_at = None
            receivable_status = "pending"
            if order["payment_status"] == "mock_paid":
                receivable_status = "paid"
                cursor.execute("SELECT MAX(processed_at) AS paid_at FROM payment_events WHERE order_id = ? AND event_status = 'processed'", (order["id"],))
                paid_at = cursor.fetchone()["paid_at"] or order["updated_at"]
            generated_ids.extend(cls._insert_record(
                cursor, order["id"], "receivable", order["total_amount"], "income",
                order["customer_name"], (today + timedelta(days=receivable_due_days)).isoformat(),
                receivable_status, paid_at, "订单应收；仅内部账务记录"
            ))

            supplier_costs = cls._supplier_costs(cursor, order["id"])
            for supplier, amount in supplier_costs.items():
                generated_ids.extend(cls._insert_record(
                    cursor, order["id"], "supplier_cost", amount, "expense", supplier,
                    (today + timedelta(days=payable_due_days)).isoformat(), "pending", None,
                    "按订单资源当前成本生成，付款状态待人工确认"
                ))
        conn.commit()
        records = cls._records_by_ids(cursor, generated_ids)
        conn.close()
        return records

    @staticmethod
    def _supplier_costs(cursor, order_id):
        costs = defaultdict(float)
        cursor.execute("SELECT resource_type, resource_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
        for item in cursor.fetchall():
            table = RESOURCE_TABLES.get(item["resource_type"])
            if not table:
                continue
            cursor.execute(f"SELECT supplier_name, cost_price FROM {table} WHERE id = ?", (item["resource_id"],))
            resource = cursor.fetchone()
            if resource is not None and resource["cost_price"] is not None:
                costs[resource["supplier_name"]] += float(resource["cost_price"]) * item["quantity"]
        return {supplier: round(amount, 2) for supplier, amount in costs.items()}

    @staticmethod
    def _insert_record(cursor, order_id, record_type, amount, direction, counterparty, due_date, status, paid_at, note):
        cursor.execute(
            """
            INSERT OR IGNORE INTO finance_records (
                order_id, record_type, amount, direction, counterparty,
                due_date, paid_at, status, risk_flags_json, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', ?)
            """,
            (order_id, record_type, round(float(amount), 2), direction, counterparty, due_date, paid_at, status, note),
        )
        inserted_ids = [cursor.lastrowid] if cursor.rowcount else []
        if record_type == "receivable":
            cursor.execute(
                """
                UPDATE finance_records
                SET amount = ?, due_date = ?, status = ?, paid_at = ?,
                    risk_flags_json = CASE WHEN ? = 'paid' THEN '[]' ELSE risk_flags_json END,
                    updated_at = ?
                WHERE order_id = ? AND record_type = 'receivable' AND counterparty = ?
                  AND status NOT IN ('cancelled', 'disputed')
                """,
                (round(float(amount), 2), due_date, status, paid_at, status,
                 datetime.now().isoformat(timespec="seconds"), order_id, counterparty),
            )
        return inserted_ids

    @staticmethod
    def _records_by_ids(cursor, ids):
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        cursor.execute(f"SELECT * FROM finance_records WHERE id IN ({placeholders}) ORDER BY id", ids)
        return [serialize_record(row) for row in cursor.fetchall()]

    @classmethod
    def refresh_overdue(cls, cursor):
        today = date.today().isoformat()
        cursor.execute(
            """
            UPDATE finance_records
            SET status = 'overdue',
                risk_flags_json = ?,
                updated_at = ?
            WHERE status = 'pending' AND due_date IS NOT NULL AND date(due_date) < date(?)
            """,
            (json.dumps(["FINANCE_RECONCILIATION_RISK"]), datetime.now().isoformat(timespec="seconds"), today),
        )

    @classmethod
    def list_records(cls, record_type=None, direction=None, status=None):
        conn = get_connection()
        cursor = conn.cursor()
        cls.refresh_overdue(cursor)
        conn.commit()
        sql = "SELECT * FROM finance_records"
        conditions = []
        params = []
        for column, value in (("record_type", record_type), ("direction", direction), ("status", status)):
            if value:
                conditions.append(f"{column} = ?")
                params.append(value)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY due_date, id"
        cursor.execute(sql, params)
        records = [serialize_record(row) for row in cursor.fetchall()]
        conn.close()
        return records

    @classmethod
    def update_status(cls, record_id, status):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM finance_records WHERE id = ?", (record_id,))
        existing = cursor.fetchone()
        if existing is None:
            conn.close()
            raise HTTPException(status_code=404, detail="未找到该财务记录")
        paid_at = existing["paid_at"]
        risks = _json_list(existing["risk_flags_json"])
        if status == "paid" and not paid_at:
            paid_at = datetime.now().isoformat(timespec="seconds")
            risks = []
        elif status in ("cancelled", "pending"):
            paid_at = None
            if status == "pending":
                risks = []
        elif status == "disputed":
            if "FINANCE_RECONCILIATION_RISK" not in risks:
                risks.append("FINANCE_RECONCILIATION_RISK")
        cursor.execute(
            "UPDATE finance_records SET status = ?, paid_at = ?, risk_flags_json = ?, updated_at = ? WHERE id = ?",
            (status, paid_at, json.dumps(risks), datetime.now().isoformat(timespec="seconds"), record_id),
        )
        conn.commit()
        cursor.execute("SELECT * FROM finance_records WHERE id = ?", (record_id,))
        record = serialize_record(cursor.fetchone())
        conn.close()
        return record

    @classmethod
    def reconciliation_report(cls, report_date=None):
        report_date = report_date or date.today()
        conn = get_connection()
        cursor = conn.cursor()
        cls.refresh_overdue(cursor)
        cursor.execute("SELECT * FROM finance_records WHERE date(created_at) <= date(?)", (report_date.isoformat(),))
        records = [serialize_record(row) for row in cursor.fetchall()]
        receivables = [row for row in records if row["record_type"] in ("receivable", "insurance_income") and row["status"] != "cancelled"]
        payables = [row for row in records if row["direction"] == "expense" and row["status"] != "cancelled"]
        total_receivable = round(sum(row["amount"] for row in receivables), 2)
        total_received = round(sum(row["amount"] for row in receivables if row["status"] == "paid"), 2)
        total_payable = round(sum(row["amount"] for row in payables), 2)
        total_paid = round(sum(row["amount"] for row in payables if row["status"] == "paid"), 2)
        gross_profit = round(total_receivable - total_payable, 2)
        risk_records = [row for row in records if row["status"] in ("overdue", "disputed")]
        risk_amount = round(sum(row["amount"] for row in risk_records), 2)
        risks = ["FINANCE_RECONCILIATION_RISK"] if risk_records else []
        recommendation = "优先核对逾期或争议记录及对应订单凭证。" if risks else "内部应收应付暂未发现逾期或争议记录。"
        cursor.execute(
            """
            INSERT INTO reconciliation_reports (
                report_date, total_receivable, total_received, total_payable,
                total_paid, gross_profit, risk_amount, risk_flags_json,
                recommendation_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_date) DO UPDATE SET
                total_receivable = excluded.total_receivable,
                total_received = excluded.total_received,
                total_payable = excluded.total_payable,
                total_paid = excluded.total_paid,
                gross_profit = excluded.gross_profit,
                risk_amount = excluded.risk_amount,
                risk_flags_json = excluded.risk_flags_json,
                recommendation_text = excluded.recommendation_text,
                created_at = datetime('now', 'localtime')
            """,
            (report_date.isoformat(), total_receivable, total_received, total_payable,
             total_paid, gross_profit, risk_amount, json.dumps(risks), recommendation),
        )
        conn.commit()
        cursor.execute("SELECT * FROM reconciliation_reports WHERE report_date = ?", (report_date.isoformat(),))
        report = serialize_report(cursor.fetchone())
        conn.close()
        return report

    @classmethod
    def risk_alerts(cls):
        records = cls.list_records()
        alerts = []
        for record in records:
            if record["status"] in ("overdue", "disputed") or record["risk_flags"]:
                alerts.append({
                    "record_id": record["id"], "order_id": record["order_id"],
                    "risk_type": "FINANCE_RECONCILIATION_RISK", "amount": record["amount"],
                    "status": record["status"], "recommended_action": "核对订单、付款凭证、金额和对手方后人工处理。",
                })
        return alerts
