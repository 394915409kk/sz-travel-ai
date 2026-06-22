from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException

from apps.backend.db import get_connection
from apps.backend.services.inventory_service import InventoryConsistencyService
from apps.backend.services.order_state_machine import OrderStateMachine
from apps.backend.services.quote_service import QuoteService, current_time


ORDER_FIELDS = """
id, order_no, inquiry_id, customer_name, phone, destination, people_count,
total_amount, paid_amount, order_status, payment_status, fulfillment_status,
created_at, updated_at
"""


def order_number():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"ORD-{timestamp}-{uuid4().hex[:8].upper()}"


def begin_critical_transaction(conn):
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("BEGIN IMMEDIATE")


class QuoteToOrderService:
    """报价转订单事务服务；库存变更只委托给 InventoryConsistencyService。"""

    @classmethod
    def convert(cls, quote_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            begin_critical_transaction(conn)
            quote = QuoteService.fetch_row(cursor, quote_id)
            if quote is None:
                raise HTTPException(status_code=404, detail="未找到该报价")
            if quote["quote_status"] == "converted_to_order":
                raise HTTPException(status_code=409, detail="该报价已经转为订单")
            if quote["quote_status"] in ("rejected", "expired"):
                raise HTTPException(status_code=400, detail="已拒绝或已过期报价不能转订单")
            if quote["quote_status"] not in ("accepted", "proposed"):
                raise HTTPException(status_code=400, detail="仅 proposed 或 accepted 报价可转订单")

            cursor.execute(
                """
                SELECT resource_type, resource_id, quantity, unit_price, total_price
                FROM quote_items WHERE quote_id = ? ORDER BY id ASC
                """,
                (quote_id,),
            )
            quote_items = cursor.fetchall()
            if not quote_items:
                raise HTTPException(status_code=400, detail="报价没有可转订单的资源明细")

            now = current_time()
            cursor.execute(
                """
                INSERT INTO orders
                (
                    order_no, inquiry_id, customer_name, phone, destination,
                    people_count, total_amount, paid_amount, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    order_number(),
                    quote["inquiry_id"],
                    quote["customer_name"],
                    quote["phone"],
                    quote["destination"],
                    quote["people_count"],
                    quote["final_price"],
                    now,
                    now,
                ),
            )
            order_id = cursor.lastrowid
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            OrderStateMachine(cursor, current_time).transition(
                cursor.fetchone(),
                "pending_payment",
            )

            for item in quote_items:
                InventoryConsistencyService(
                    cursor,
                    item["resource_type"],
                ).lock_stock(
                    order_id,
                    item["resource_id"],
                    item["quantity"],
                )
                cursor.execute(
                    """
                    INSERT INTO order_items
                    (
                        order_id, resource_type, resource_id, quantity,
                        unit_price, total_price
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        item["resource_type"],
                        item["resource_id"],
                        item["quantity"],
                        item["unit_price"],
                        item["total_price"],
                    ),
                )

            cursor.execute(
                """
                UPDATE quotes
                SET quote_status = 'converted_to_order', converted_order_id = ?,
                    updated_at = ?
                WHERE id = ?
                  AND quote_status IN ('accepted', 'proposed')
                  AND converted_order_id IS NULL
                """,
                (order_id, now, quote_id),
            )
            if cursor.rowcount != 1:
                raise HTTPException(status_code=409, detail="报价已被并发转换或状态已变化")

            conn.commit()
            order = cls._fetch_order_detail(conn, order_id)
            converted_quote = QuoteService.fetch_detail(conn, quote_id)
        except Exception:
            conn.rollback()
            conn.close()
            raise
        conn.close()
        return {"order": order, "quote": converted_quote}

    @staticmethod
    def _fetch_order_detail(conn, order_id):
        cursor = conn.cursor()
        cursor.execute(f"SELECT {ORDER_FIELDS} FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        cursor.execute(
            """
            SELECT id, order_id, resource_type, resource_id, quantity,
                   unit_price, total_price
            FROM order_items WHERE order_id = ? ORDER BY id ASC
            """,
            (order_id,),
        )
        return {**dict(order), "items": [dict(item) for item in cursor.fetchall()]}
