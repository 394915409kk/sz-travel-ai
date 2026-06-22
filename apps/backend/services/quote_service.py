import json
from datetime import date, datetime
from math import ceil
from uuid import uuid4

from fastapi import HTTPException

from apps.backend.db import get_connection
from apps.backend.services.inventory_service import RESOURCE_TABLES
from apps.backend.services.pricing_service import PricingService


QUOTE_FIELDS = """
id, quote_no, inquiry_id, customer_name, phone, destination, people_count,
customer_budget, target_margin, base_cost, base_price, dynamic_adjustment,
final_price, estimated_profit, estimated_margin, quote_status,
pricing_strategy, risk_flags, recommendation, departure_date,
converted_order_id, created_at, updated_at
"""

RESOURCE_TYPES = (
    "transport",
    "hotel_room",
    "attraction_ticket",
    "restaurant_meal",
    "activity",
)


def current_time():
    return datetime.now().isoformat(timespec="seconds")


def quote_number():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"QTE-{timestamp}-{uuid4().hex[:8].upper()}"


def begin_critical_transaction(conn):
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("BEGIN IMMEDIATE")


def serialize_quote(row, items=None):
    quote = dict(row)
    try:
        risk_flags = json.loads(quote.get("risk_flags") or "[]")
        quote["risk_flags"] = risk_flags if isinstance(risk_flags, list) else []
    except json.JSONDecodeError:
        quote["risk_flags"] = []
    if items is not None:
        quote["items"] = items
    return quote


class QuoteService:
    @classmethod
    def generate(cls, payload):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            inquiry = cls._fetch_inquiry(cursor, payload.get("inquiry_id"))
            customer_name = payload.get("customer_name") or cls._value(
                inquiry, "customer_name"
            )
            phone = (
                payload.get("phone")
                if payload.get("phone") is not None
                else cls._value(inquiry, "phone")
            )
            destination = payload.get("destination") or cls._value(
                inquiry, "destination"
            )
            people_count = payload.get("people_count") or cls._value(
                inquiry, "people_count"
            ) or 1
            customer_budget = (
                payload.get("customer_budget")
                if payload.get("customer_budget") is not None
                else cls._value(inquiry, "budget")
            )
            departure_date = payload.get("departure_date") or cls._value(
                inquiry, "departure_date"
            )

            if not customer_name or not destination:
                raise HTTPException(
                    status_code=422,
                    detail="报价 customer_name 和 destination 不能为空",
                )

            requested_items = payload.get("resource_items") or []
            if requested_items:
                resource_items = cls._resolve_requested_resources(
                    cursor,
                    requested_items,
                    departure_date,
                )
            else:
                resource_items = cls._auto_select_resources(
                    cursor,
                    destination,
                    int(people_count),
                    departure_date,
                )
            if not resource_items:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "没有可用于生成报价的在售资源",
                        "risk_flags": ["no_available_resource"],
                    },
                )

            pricing = PricingService.calculate(
                resource_items,
                payload["target_margin"],
                customer_budget=customer_budget,
                departure_date=departure_date,
            )
            now = current_time()
            cursor.execute(
                """
                INSERT INTO quotes
                (
                    quote_no, inquiry_id, customer_name, phone, destination,
                    people_count, customer_budget, target_margin, base_cost,
                    base_price, dynamic_adjustment, final_price,
                    estimated_profit, estimated_margin, quote_status,
                    pricing_strategy, risk_flags, recommendation,
                    departure_date, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft',
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    quote_number(),
                    payload.get("inquiry_id"),
                    customer_name,
                    phone,
                    destination,
                    int(people_count),
                    customer_budget,
                    payload["target_margin"],
                    pricing["base_cost"],
                    pricing["base_price"],
                    pricing["dynamic_adjustment"],
                    pricing["final_price"],
                    pricing["estimated_profit"],
                    pricing["estimated_margin"],
                    payload["pricing_strategy"],
                    json.dumps(pricing["risk_flags"], ensure_ascii=False),
                    pricing["recommendation"],
                    cls._iso_date(departure_date),
                    now,
                    now,
                ),
            )
            quote_id = cursor.lastrowid
            for item in pricing["items"]:
                cursor.execute(
                    """
                    INSERT INTO quote_items
                    (
                        quote_id, resource_type, resource_id, resource_name,
                        quantity, unit_cost, unit_price, total_cost,
                        total_price, margin, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        quote_id,
                        item["resource_type"],
                        item["resource_id"],
                        item["resource_name"],
                        item["quantity"],
                        item["unit_cost"],
                        item["unit_price"],
                        item["total_cost"],
                        item["total_price"],
                        item["margin"],
                        now,
                    ),
                )
            conn.commit()
            result = cls.fetch_detail(conn, quote_id)
        except Exception:
            conn.rollback()
            conn.close()
            raise
        conn.close()
        return result

    @classmethod
    def list_quotes(
        cls,
        destination=None,
        quote_status=None,
        inquiry_id=None,
        date_from=None,
        date_to=None,
        min_margin=None,
        max_price=None,
    ):
        sql = f"SELECT {QUOTE_FIELDS} FROM quotes"
        conditions = []
        params = []
        if destination:
            conditions.append("destination LIKE ?")
            params.append(f"%{destination}%")
        for column, value in (
            ("quote_status", quote_status),
            ("inquiry_id", inquiry_id),
        ):
            if value is not None:
                conditions.append(f"{column} = ?")
                params.append(value)
        if date_from is not None:
            conditions.append("date(created_at) >= date(?)")
            params.append(cls._iso_date(date_from))
        if date_to is not None:
            conditions.append("date(created_at) <= date(?)")
            params.append(cls._iso_date(date_to))
        if min_margin is not None:
            conditions.append("estimated_margin >= ?")
            params.append(min_margin)
        if max_price is not None:
            conditions.append("final_price <= ?")
            params.append(max_price)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY id DESC"

        conn = get_connection()
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [serialize_quote(row) for row in rows]

    @classmethod
    def get(cls, quote_id):
        conn = get_connection()
        quote = cls.fetch_detail(conn, quote_id)
        conn.close()
        if quote is None:
            raise HTTPException(status_code=404, detail="未找到该报价")
        return quote

    @classmethod
    def update_status(cls, quote_id, target_status):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            begin_critical_transaction(conn)
            row = cls.fetch_row(cursor, quote_id)
            if row is None:
                raise HTTPException(status_code=404, detail="未找到该报价")
            current_status = row["quote_status"]
            if current_status == "converted_to_order" and target_status != current_status:
                raise HTTPException(status_code=400, detail="已转订单报价不能改回其他状态")
            if target_status == "converted_to_order" and row["converted_order_id"] is None:
                raise HTTPException(
                    status_code=400,
                    detail="请通过报价转订单接口更新 converted_to_order 状态",
                )
            if current_status != target_status:
                cursor.execute(
                    """
                    UPDATE quotes SET quote_status = ?, updated_at = ?
                    WHERE id = ? AND quote_status = ?
                    """,
                    (target_status, current_time(), quote_id, current_status),
                )
                if cursor.rowcount != 1:
                    raise HTTPException(status_code=409, detail="报价状态已被并发修改")
            conn.commit()
            result = cls.fetch_detail(conn, quote_id)
        except Exception:
            conn.rollback()
            conn.close()
            raise
        conn.close()
        return result

    @staticmethod
    def fetch_row(cursor, quote_id):
        cursor.execute(f"SELECT {QUOTE_FIELDS} FROM quotes WHERE id = ?", (quote_id,))
        return cursor.fetchone()

    @classmethod
    def fetch_detail(cls, conn, quote_id):
        cursor = conn.cursor()
        row = cls.fetch_row(cursor, quote_id)
        if row is None:
            return None
        cursor.execute(
            """
            SELECT id, quote_id, resource_type, resource_id, resource_name,
                   quantity, unit_cost, unit_price, total_cost, total_price,
                   margin, created_at
            FROM quote_items WHERE quote_id = ? ORDER BY id ASC
            """,
            (quote_id,),
        )
        return serialize_quote(row, [dict(item) for item in cursor.fetchall()])

    @staticmethod
    def _fetch_inquiry(cursor, inquiry_id):
        if inquiry_id is None:
            return None
        cursor.execute(
            """
            SELECT id, customer_name, phone, destination, people_count,
                   budget, departure_date
            FROM inquiries WHERE id = ?
            """,
            (inquiry_id,),
        )
        inquiry = cursor.fetchone()
        if inquiry is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "未找到该客户咨询记录",
                    "risk_flags": ["inquiry_not_found"],
                },
            )
        return inquiry

    @classmethod
    def _resolve_requested_resources(cls, cursor, requested_items, departure_date):
        grouped = {}
        for requested in requested_items:
            key = (requested["resource_type"], requested["resource_id"])
            grouped[key] = grouped.get(key, 0) + requested["quantity"]

        resolved = []
        for (resource_type, resource_id), quantity in grouped.items():
            resolved.append(
                cls._resolve_resource(
                    cursor,
                    resource_type,
                    resource_id,
                    quantity,
                    departure_date,
                )
            )
        return resolved

    @classmethod
    def _auto_select_resources(
        cls,
        cursor,
        destination,
        people_count,
        departure_date,
    ):
        selected = []
        for resource_type in RESOURCE_TYPES:
            table_name = RESOURCE_TABLES[resource_type]
            cursor.execute(
                f"""
                SELECT * FROM {table_name}
                WHERE status = 'active' AND destination = ?
                ORDER BY cost_price ASC, sale_price ASC, id ASC
                """,
                (destination,),
            )
            for row in cursor.fetchall():
                quantity = people_count
                if resource_type == "hotel_room":
                    quantity = ceil(people_count / max(int(row["max_occupancy"]), 1))
                if not cls._resource_available_on(row, departure_date):
                    continue
                available = cls._available_quantity(row)
                if available < quantity:
                    continue
                selected.append(
                    cls._resource_payload(resource_type, row, quantity, available)
                )
                break
        return selected

    @classmethod
    def _resolve_resource(
        cls,
        cursor,
        resource_type,
        resource_id,
        quantity,
        departure_date,
    ):
        table_name = RESOURCE_TABLES[resource_type]
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = ?", (resource_id,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="未找到报价资源")
        if row["status"] != "active":
            raise HTTPException(status_code=400, detail="报价资源未启用")
        if not cls._resource_available_on(row, departure_date):
            raise HTTPException(status_code=400, detail="报价资源在出发日期不可售")
        available = cls._available_quantity(row)
        if available < quantity:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "报价资源库存不足",
                    "risk_flags": ["no_available_resource"],
                },
            )
        return cls._resource_payload(resource_type, row, quantity, available)

    @staticmethod
    def _resource_payload(resource_type, row, quantity, available):
        cost_price = row["cost_price"]
        return {
            "resource_type": resource_type,
            "resource_id": row["id"],
            "resource_name": row["resource_name"],
            "quantity": int(quantity),
            "unit_cost": 0 if cost_price is None else float(cost_price),
            "listed_unit_price": float(row["sale_price"] or 0),
            "available_quantity": available,
            "cost_missing": cost_price is None or float(cost_price) <= 0,
        }

    @staticmethod
    def _available_quantity(row):
        return (
            int(row["stock_quantity"])
            - int(row["sold_quantity"])
            - int(row["reserved_quantity"])
        )

    @classmethod
    def _resource_available_on(cls, row, departure_date):
        if departure_date is None:
            return True
        target = cls._iso_date(departure_date)
        raw_dates = row["available_dates"]
        if raw_dates:
            try:
                dates = json.loads(raw_dates)
            except json.JSONDecodeError:
                dates = []
            if isinstance(dates, list) and dates:
                return target in dates
        return (
            (row["available_start_date"] is None or row["available_start_date"] <= target)
            and (row["available_end_date"] is None or row["available_end_date"] >= target)
        )

    @staticmethod
    def _value(row, field):
        return row[field] if row is not None else None

    @staticmethod
    def _iso_date(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)
