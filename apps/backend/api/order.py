from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.backend.db import get_connection


router = APIRouter()

OrderStatus = Literal[
    "draft",
    "pending_payment",
    "paid",
    "fulfilling",
    "completed",
    "cancelled",
]
PaymentStatus = Literal["unpaid", "mock_paid", "refunded"]
FulfillmentStatus = Literal[
    "pending",
    "documents_pending",
    "contract_pending",
    "ready_to_travel",
    "in_progress",
    "completed",
]
ResourceType = Literal[
    "transport",
    "hotel_room",
    "attraction_ticket",
    "restaurant_meal",
    "activity",
]
InsuranceStatus = Literal["active", "inactive"]
VerificationStatus = Literal["pending", "verified", "rejected"]
ReminderStatus = Literal["pending", "completed", "cancelled"]

RESOURCE_TABLES = {
    "transport": "travel_transport_resources",
    "hotel_room": "hotel_room_resources",
    "attraction_ticket": "attraction_ticket_resources",
    "restaurant_meal": "restaurant_meal_resources",
    "activity": "activity_resources",
}

ORDER_FIELDS = """
id, order_no, inquiry_id, customer_name, phone, destination, people_count,
total_amount, paid_amount, order_status, payment_status, fulfillment_status,
created_at, updated_at
"""
ORDER_ITEM_FIELDS = """
id, order_id, resource_type, resource_id, quantity, unit_price, total_price
"""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrderItemCreate(StrictModel):
    resource_type: ResourceType
    resource_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    unit_price: float | None = Field(default=None, ge=0)


class OrderCreate(StrictModel):
    inquiry_id: int | None = Field(default=None, gt=0)
    customer_name: str | None = Field(default=None, min_length=1)
    phone: str | None = None
    destination: str | None = Field(default=None, min_length=1)
    people_count: int | None = Field(default=None, gt=0)
    total_amount: float | None = Field(default=None, ge=0)
    items: list[OrderItemCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_manual_order(self):
        if self.inquiry_id is None:
            if not self.customer_name:
                raise ValueError("手动创建订单时 customer_name 必填")
            if not self.destination:
                raise ValueError("手动创建订单时 destination 必填")
        return self


class OrderStatusUpdate(StrictModel):
    order_status: OrderStatus


class OrderDocumentCreate(StrictModel):
    customer_name: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    document_number: str = Field(min_length=1)
    file_name: str | None = None
    file_url: str | None = None
    verified_status: VerificationStatus = "pending"


class InsuranceProductCreate(StrictModel):
    name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    coverage_summary: str | None = None
    price: float = Field(ge=0)
    status: InsuranceStatus = "active"


class OrderInsuranceCreate(StrictModel):
    insurance_product_id: int = Field(gt=0)
    insured_customer_name: str = Field(min_length=1)


class ContractGenerateRequest(StrictModel):
    contract_content: str | None = None


class ReminderCreate(StrictModel):
    reminder_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    message: str = Field(min_length=1)
    remind_at: datetime
    status: ReminderStatus = "pending"


class ReminderStatusUpdate(StrictModel):
    status: ReminderStatus


def current_time():
    return datetime.now().isoformat(timespec="seconds")


def generated_number(prefix):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}-{uuid4().hex[:8].upper()}"


def fetch_order(cursor, order_id):
    cursor.execute(
        f"SELECT {ORDER_FIELDS} FROM orders WHERE id = ?",
        (order_id,),
    )
    return cursor.fetchone()


def fetch_order_items(cursor, order_id):
    cursor.execute(
        f"SELECT {ORDER_ITEM_FIELDS} FROM order_items "
        "WHERE order_id = ? ORDER BY id ASC",
        (order_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def serialize_order(row, items=None):
    result = dict(row)
    if items is not None:
        result["items"] = items
    return result


def fetch_order_detail(conn, order_id):
    cursor = conn.cursor()
    row = fetch_order(cursor, order_id)
    if row is None:
        return None
    return serialize_order(row, fetch_order_items(cursor, order_id))


def fetch_resource(cursor, resource_type, resource_id):
    table_name = RESOURCE_TABLES[resource_type]
    cursor.execute(
        f"""
        SELECT id, sale_price, stock_quantity, sold_quantity,
               reserved_quantity, status
        FROM {table_name}
        WHERE id = ?
        """,
        (resource_id,),
    )
    return table_name, cursor.fetchone()


def reserve_inventory(cursor, item):
    table_name, resource = fetch_resource(
        cursor,
        item.resource_type,
        item.resource_id,
    )
    if resource is None:
        raise HTTPException(status_code=404, detail="未找到订单资源")
    if resource["status"] != "active":
        raise HTTPException(status_code=400, detail="订单资源未启用")

    available = (
        resource["stock_quantity"]
        - resource["sold_quantity"]
        - resource["reserved_quantity"]
    )
    if available < item.quantity:
        raise HTTPException(status_code=400, detail="库存不足")

    cursor.execute(
        f"""
        UPDATE {table_name}
        SET reserved_quantity = reserved_quantity + ?
        WHERE id = ?
          AND stock_quantity - sold_quantity - reserved_quantity >= ?
        """,
        (item.quantity, item.resource_id, item.quantity),
    )
    if cursor.rowcount != 1:
        raise HTTPException(status_code=400, detail="库存不足")

    unit_price = (
        item.unit_price if item.unit_price is not None else resource["sale_price"]
    )
    return round(float(unit_price), 2)


def transfer_reserved_to_sold(cursor, item):
    table_name = RESOURCE_TABLES[item["resource_type"]]
    cursor.execute(
        f"""
        UPDATE {table_name}
        SET reserved_quantity = reserved_quantity - ?,
            sold_quantity = sold_quantity + ?
        WHERE id = ? AND reserved_quantity >= ?
        """,
        (
            item["quantity"],
            item["quantity"],
            item["resource_id"],
            item["quantity"],
        ),
    )
    if cursor.rowcount != 1:
        raise HTTPException(status_code=409, detail="订单预留库存状态异常")


def release_reserved_inventory(cursor, item):
    table_name = RESOURCE_TABLES[item["resource_type"]]
    cursor.execute(
        f"""
        UPDATE {table_name}
        SET reserved_quantity = reserved_quantity - ?
        WHERE id = ? AND reserved_quantity >= ?
        """,
        (item["quantity"], item["resource_id"], item["quantity"]),
    )
    if cursor.rowcount != 1:
        raise HTTPException(status_code=409, detail="订单预留库存状态异常")


@router.post("/orders")
def create_order(request: OrderCreate):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN IMMEDIATE")
        inquiry = None
        if request.inquiry_id is not None:
            cursor.execute(
                """
                SELECT id, customer_name, phone, destination, people_count
                FROM inquiries WHERE id = ?
                """,
                (request.inquiry_id,),
            )
            inquiry = cursor.fetchone()
            if inquiry is None:
                raise HTTPException(status_code=404, detail="未找到该客户咨询记录")

        customer_name = request.customer_name or (
            inquiry["customer_name"] if inquiry is not None else None
        )
        phone = request.phone if request.phone is not None else (
            inquiry["phone"] if inquiry is not None else None
        )
        destination = request.destination or (
            inquiry["destination"] if inquiry is not None else None
        )
        people_count = request.people_count or (
            inquiry["people_count"] if inquiry is not None else None
        ) or 1
        if not customer_name or not destination:
            raise HTTPException(
                status_code=422,
                detail="订单 customer_name 和 destination 不能为空",
            )

        now = current_time()
        cursor.execute(
            """
            INSERT INTO orders
            (
                order_no, inquiry_id, customer_name, phone, destination,
                people_count, total_amount, paid_amount, order_status,
                payment_status, fulfillment_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'pending_payment',
                    'unpaid', 'pending', ?, ?)
            """,
            (
                generated_number("ORD"),
                request.inquiry_id,
                customer_name,
                phone,
                destination,
                people_count,
                now,
                now,
            ),
        )
        order_id = cursor.lastrowid

        items_total = 0.0
        for item in request.items:
            unit_price = reserve_inventory(cursor, item)
            total_price = round(unit_price * item.quantity, 2)
            items_total = round(items_total + total_price, 2)
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
                    item.resource_type,
                    item.resource_id,
                    item.quantity,
                    unit_price,
                    total_price,
                ),
            )

        total_amount = (
            round(float(request.total_amount), 2)
            if request.total_amount is not None
            else items_total
        )
        cursor.execute(
            "UPDATE orders SET total_amount = ? WHERE id = ?",
            (total_amount, order_id),
        )
        conn.commit()
        result = fetch_order_detail(conn, order_id)
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return {"success": True, "order": result}


@router.get("/orders")
def get_orders(
    order_status: OrderStatus | None = None,
    payment_status: PaymentStatus | None = None,
    fulfillment_status: FulfillmentStatus | None = None,
    inquiry_id: int | None = Query(default=None, gt=0),
):
    sql = f"SELECT {ORDER_FIELDS} FROM orders"
    conditions = []
    params = []
    for column, value in (
        ("order_status", order_status),
        ("payment_status", payment_status),
        ("fulfillment_status", fulfillment_status),
        ("inquiry_id", inquiry_id),
    ):
        if value is not None:
            conditions.append(f"{column} = ?")
            params.append(value)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY id DESC"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    orders = [serialize_order(row) for row in cursor.fetchall()]
    conn.close()
    return {"success": True, "count": len(orders), "orders": orders}


@router.get("/orders/{order_id}")
def get_order(order_id: int):
    conn = get_connection()
    order = fetch_order_detail(conn, order_id)
    conn.close()
    if order is None:
        raise HTTPException(status_code=404, detail="未找到该订单")
    return {"success": True, "order": order}


@router.patch("/orders/{order_id}/status")
def update_order_status(order_id: int, request: OrderStatusUpdate):
    allowed_transitions = {
        "draft": {"pending_payment", "cancelled"},
        "pending_payment": {"cancelled"},
        "paid": {"fulfilling", "cancelled"},
        "fulfilling": {"completed", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }
    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN IMMEDIATE")
        order = fetch_order(cursor, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="未找到该订单")
        current_status = order["order_status"]
        next_status = request.order_status
        if current_status == next_status:
            conn.commit()
            result = fetch_order_detail(conn, order_id)
            conn.close()
            return {"success": True, "order": result}
        if next_status == "paid":
            raise HTTPException(status_code=400, detail="请使用 mock-payment 完成支付")
        if next_status not in allowed_transitions[current_status]:
            raise HTTPException(status_code=400, detail="不允许的订单状态流转")

        if next_status == "cancelled" and order["payment_status"] == "unpaid":
            for item in fetch_order_items(cursor, order_id):
                release_reserved_inventory(cursor, item)

        fulfillment_status = order["fulfillment_status"]
        if next_status == "fulfilling":
            fulfillment_status = "in_progress"
        elif next_status == "completed":
            fulfillment_status = "completed"

        cursor.execute(
            """
            UPDATE orders
            SET order_status = ?, fulfillment_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (next_status, fulfillment_status, current_time(), order_id),
        )
        conn.commit()
        result = fetch_order_detail(conn, order_id)
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return {"success": True, "order": result}


@router.post("/orders/{order_id}/mock-payment")
def mock_payment(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN IMMEDIATE")
        order = fetch_order(cursor, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="未找到该订单")
        if order["order_status"] == "cancelled":
            raise HTTPException(status_code=400, detail="已取消订单不能支付")
        if order["payment_status"] == "mock_paid":
            raise HTTPException(status_code=409, detail="订单已完成模拟支付")
        if order["payment_status"] != "unpaid":
            raise HTTPException(status_code=400, detail="当前支付状态不能模拟支付")

        for item in fetch_order_items(cursor, order_id):
            transfer_reserved_to_sold(cursor, item)

        cursor.execute(
            "SELECT COUNT(*) AS count FROM order_documents WHERE order_id = ?",
            (order_id,),
        )
        has_documents = cursor.fetchone()["count"] > 0
        cursor.execute(
            """
            SELECT COUNT(*) AS count FROM order_contracts
            WHERE order_id = ? AND contract_status = 'signed'
            """,
            (order_id,),
        )
        has_signed_contract = cursor.fetchone()["count"] > 0
        if has_signed_contract:
            fulfillment_status = "ready_to_travel"
        elif has_documents:
            fulfillment_status = "contract_pending"
        else:
            fulfillment_status = "documents_pending"

        cursor.execute(
            """
            UPDATE orders
            SET payment_status = 'mock_paid', order_status = 'paid',
                paid_amount = total_amount, fulfillment_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (fulfillment_status, current_time(), order_id),
        )
        conn.commit()
        result = fetch_order_detail(conn, order_id)
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return {"success": True, "order": result}


@router.post("/orders/{order_id}/documents")
def create_order_document(order_id: int, request: OrderDocumentCreate):
    conn = get_connection()
    cursor = conn.cursor()
    order = fetch_order(cursor, order_id)
    if order is None:
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该订单")
    if order["order_status"] == "cancelled":
        conn.close()
        raise HTTPException(status_code=400, detail="已取消订单不能新增证件")

    cursor.execute(
        """
        INSERT INTO order_documents
        (
            order_id, customer_name, document_type, document_number,
            file_name, file_url, ocr_status, ocr_raw_text,
            verified_status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, ?, ?)
        """,
        (
            order_id,
            request.customer_name,
            request.document_type,
            request.document_number,
            request.file_name,
            request.file_url,
            request.verified_status,
            current_time(),
        ),
    )
    document_id = cursor.lastrowid
    if (
        order["payment_status"] == "mock_paid"
        and order["fulfillment_status"] == "documents_pending"
    ):
        cursor.execute(
            """
            UPDATE orders
            SET fulfillment_status = 'contract_pending', updated_at = ?
            WHERE id = ?
            """,
            (current_time(), order_id),
        )
    conn.commit()
    cursor.execute("SELECT * FROM order_documents WHERE id = ?", (document_id,))
    result = dict(cursor.fetchone())
    conn.close()
    return {"success": True, "document": result}


@router.get("/orders/{order_id}/documents")
def get_order_documents(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    if fetch_order(cursor, order_id) is None:
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该订单")
    cursor.execute(
        "SELECT * FROM order_documents WHERE order_id = ? ORDER BY id ASC",
        (order_id,),
    )
    documents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"success": True, "count": len(documents), "documents": documents}


@router.post("/insurance-products")
def create_insurance_product(request: InsuranceProductCreate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO insurance_products
        (name, provider, coverage_summary, price, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            request.name,
            request.provider,
            request.coverage_summary,
            round(request.price, 2),
            request.status,
        ),
    )
    product_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM insurance_products WHERE id = ?", (product_id,))
    result = dict(cursor.fetchone())
    conn.close()
    return {"success": True, "insurance_product": result}


@router.get("/insurance-products")
def get_insurance_products(status: InsuranceStatus | None = None):
    conn = get_connection()
    cursor = conn.cursor()
    if status is None:
        cursor.execute("SELECT * FROM insurance_products ORDER BY id DESC")
    else:
        cursor.execute(
            "SELECT * FROM insurance_products WHERE status = ? ORDER BY id DESC",
            (status,),
        )
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"success": True, "count": len(products), "insurance_products": products}


@router.post("/orders/{order_id}/insurances")
def create_order_insurance(order_id: int, request: OrderInsuranceCreate):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN IMMEDIATE")
        order = fetch_order(cursor, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="未找到该订单")
        if order["order_status"] in ("completed", "cancelled"):
            raise HTTPException(status_code=400, detail="当前订单不能新增保险")
        cursor.execute(
            "SELECT * FROM insurance_products WHERE id = ?",
            (request.insurance_product_id,),
        )
        product = cursor.fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="未找到该保险产品")
        if product["status"] != "active":
            raise HTTPException(status_code=400, detail="仅 active 保险产品可选")

        price = round(float(product["price"]), 2)
        cursor.execute(
            """
            INSERT INTO order_insurances
            (order_id, insurance_product_id, insured_customer_name, price)
            VALUES (?, ?, ?, ?)
            """,
            (
                order_id,
                request.insurance_product_id,
                request.insured_customer_name,
                price,
            ),
        )
        insurance_id = cursor.lastrowid
        cursor.execute(
            """
            UPDATE orders
            SET total_amount = total_amount + ?, updated_at = ?
            WHERE id = ?
            """,
            (price, current_time(), order_id),
        )
        conn.commit()
        cursor.execute("SELECT * FROM order_insurances WHERE id = ?", (insurance_id,))
        result = dict(cursor.fetchone())
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return {"success": True, "order_insurance": result}


@router.get("/orders/{order_id}/insurances")
def get_order_insurances(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    if fetch_order(cursor, order_id) is None:
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该订单")
    cursor.execute(
        """
        SELECT oi.*, ip.name AS insurance_name, ip.provider
        FROM order_insurances AS oi
        JOIN insurance_products AS ip ON ip.id = oi.insurance_product_id
        WHERE oi.order_id = ? ORDER BY oi.id ASC
        """,
        (order_id,),
    )
    insurances = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"success": True, "count": len(insurances), "insurances": insurances}


@router.post("/orders/{order_id}/contracts/generate")
def generate_contract(
    order_id: int,
    request: ContractGenerateRequest | None = None,
):
    conn = get_connection()
    cursor = conn.cursor()
    order = fetch_order(cursor, order_id)
    if order is None:
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该订单")
    if order["order_status"] == "cancelled":
        conn.close()
        raise HTTPException(status_code=400, detail="已取消订单不能生成合同")

    content = request.contract_content if request else None
    if not content:
        content = (
            f"订单 {order['order_no']} 旅游服务合同（MVP 模板记录）。"
            f"客户：{order['customer_name']}；目的地：{order['destination']}；"
            f"订单金额：{order['total_amount']}。"
        )
    cursor.execute(
        """
        INSERT INTO order_contracts
        (order_id, contract_no, contract_status, contract_content, signed_at)
        VALUES (?, ?, 'generated', ?, NULL)
        """,
        (order_id, generated_number("CTR"), content),
    )
    contract_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM order_contracts WHERE id = ?", (contract_id,))
    result = dict(cursor.fetchone())
    conn.close()
    return {"success": True, "contract": result}


@router.get("/orders/{order_id}/contracts")
def get_order_contracts(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    if fetch_order(cursor, order_id) is None:
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该订单")
    cursor.execute(
        "SELECT * FROM order_contracts WHERE order_id = ? ORDER BY id ASC",
        (order_id,),
    )
    contracts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"success": True, "count": len(contracts), "contracts": contracts}


@router.post("/orders/{order_id}/contracts/{contract_id}/mock-sign")
def mock_sign_contract(order_id: int, contract_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN IMMEDIATE")
        order = fetch_order(cursor, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="未找到该订单")
        if order["order_status"] == "cancelled":
            raise HTTPException(status_code=400, detail="已取消订单不能签署合同")
        cursor.execute(
            "SELECT * FROM order_contracts WHERE id = ? AND order_id = ?",
            (contract_id, order_id),
        )
        contract = cursor.fetchone()
        if contract is None:
            raise HTTPException(status_code=404, detail="未找到该订单合同")
        if contract["contract_status"] != "signed":
            cursor.execute(
                """
                UPDATE order_contracts
                SET contract_status = 'signed', signed_at = ?
                WHERE id = ?
                """,
                (current_time(), contract_id),
            )
        if order["payment_status"] == "mock_paid":
            cursor.execute(
                """
                UPDATE orders
                SET fulfillment_status = 'ready_to_travel', updated_at = ?
                WHERE id = ?
                """,
                (current_time(), order_id),
            )
        conn.commit()
        cursor.execute("SELECT * FROM order_contracts WHERE id = ?", (contract_id,))
        result = dict(cursor.fetchone())
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return {"success": True, "contract": result}


@router.post("/orders/{order_id}/reminders")
def create_order_reminder(order_id: int, request: ReminderCreate):
    conn = get_connection()
    cursor = conn.cursor()
    if fetch_order(cursor, order_id) is None:
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该订单")
    cursor.execute(
        """
        INSERT INTO order_reminders
        (order_id, reminder_type, title, message, remind_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            request.reminder_type,
            request.title,
            request.message,
            request.remind_at.isoformat(timespec="seconds"),
            request.status,
        ),
    )
    reminder_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM order_reminders WHERE id = ?", (reminder_id,))
    result = dict(cursor.fetchone())
    conn.close()
    return {"success": True, "reminder": result}


@router.get("/orders/{order_id}/reminders")
def get_order_reminders(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    if fetch_order(cursor, order_id) is None:
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该订单")
    cursor.execute(
        "SELECT * FROM order_reminders WHERE order_id = ? ORDER BY remind_at, id",
        (order_id,),
    )
    reminders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"success": True, "count": len(reminders), "reminders": reminders}


@router.patch("/orders/{order_id}/reminders/{reminder_id}/status")
def update_order_reminder_status(
    order_id: int,
    reminder_id: int,
    request: ReminderStatusUpdate,
):
    conn = get_connection()
    cursor = conn.cursor()
    if fetch_order(cursor, order_id) is None:
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该订单")
    cursor.execute(
        """
        UPDATE order_reminders SET status = ?
        WHERE id = ? AND order_id = ?
        """,
        (request.status, reminder_id, order_id),
    )
    if cursor.rowcount != 1:
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该订单提醒")
    conn.commit()
    cursor.execute("SELECT * FROM order_reminders WHERE id = ?", (reminder_id,))
    result = dict(cursor.fetchone())
    conn.close()
    return {"success": True, "reminder": result}
