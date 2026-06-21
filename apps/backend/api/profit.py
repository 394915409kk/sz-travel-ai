from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException

from apps.backend.db import get_connection
from apps.backend.services.profit_service import ProfitService


router = APIRouter(prefix="/profit", tags=["profit"])

OrderStatus = Literal[
    "draft",
    "pending_payment",
    "paid",
    "fulfilling",
    "completed",
    "cancelled",
]
PaymentStatus = Literal["unpaid", "mock_paid", "refunded"]


def profit_filters(
    destination,
    date_from,
    date_to,
    sales,
    order_status,
    payment_status,
):
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from 不能晚于 date_to")
    return {
        "destination": destination,
        "date_from": date_from,
        "date_to": date_to,
        "sales": sales,
        "order_status": order_status,
        "payment_status": payment_status,
    }


@router.get("/orders/high-profit")
def get_high_profit_orders(
    destination: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sales: str | None = None,
    order_status: OrderStatus | None = None,
    payment_status: PaymentStatus | None = None,
):
    filters = profit_filters(
        destination,
        date_from,
        date_to,
        sales,
        order_status,
        payment_status,
    )
    conn = get_connection()
    try:
        orders = ProfitService(conn).list_order_profits(**filters)
        orders = [
            order for order in orders if order["profit_level"] == "high_profit"
        ]
    finally:
        conn.close()
    return {"success": True, "count": len(orders), "orders": orders}


@router.get("/orders/risk")
def get_risk_orders(
    destination: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sales: str | None = None,
    order_status: OrderStatus | None = None,
    payment_status: PaymentStatus | None = None,
):
    filters = profit_filters(
        destination,
        date_from,
        date_to,
        sales,
        order_status,
        payment_status,
    )
    conn = get_connection()
    try:
        orders = ProfitService(conn).list_order_profits(**filters)
        orders = [order for order in orders if order["risk_flags"]]
    finally:
        conn.close()
    return {"success": True, "count": len(orders), "orders": orders}


@router.get("/summary")
def get_profit_summary(
    destination: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sales: str | None = None,
    order_status: OrderStatus | None = None,
    payment_status: PaymentStatus | None = None,
):
    filters = profit_filters(
        destination,
        date_from,
        date_to,
        sales,
        order_status,
        payment_status,
    )
    conn = get_connection()
    try:
        summary = ProfitService(conn).get_summary(**filters)
    finally:
        conn.close()
    return {"success": True, **summary}


@router.get("/orders/{order_id}")
def get_order_profit(order_id: int):
    conn = get_connection()
    try:
        profit = ProfitService(conn).get_order_profit(order_id)
    finally:
        conn.close()
    if profit is None:
        raise HTTPException(status_code=404, detail="未找到该订单")
    return {"success": True, **profit}
