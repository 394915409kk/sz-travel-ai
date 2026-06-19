from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from apps.backend.db import get_connection

router = APIRouter()

Priority = Literal["high", "medium", "low"]

ALLOWED_STATUSES = [
    "new",
    "contacted",
    "interested",
    "quoted",
    "confirmed",
    "lost"
]

INQUIRY_SELECT_FIELDS = """
id, customer_name, phone, destination, people_count, budget,
departure_date, message, follow_status, source, assigned_sales,
priority, last_contact_at, next_follow_up_at, created_at
"""


def format_datetime(value: datetime | None):
    if value is None:
        return None
    return value.isoformat(timespec="seconds")


def serialize_inquiry(row):
    return {
        "id": row["id"],
        "customer_name": row["customer_name"],
        "phone": row["phone"],
        "destination": row["destination"],
        "people_count": row["people_count"],
        "budget": row["budget"],
        "departure_date": row["departure_date"],
        "message": row["message"],
        "follow_status": row["follow_status"],
        "source": row["source"],
        "assigned_sales": row["assigned_sales"],
        "priority": row["priority"],
        "last_contact_at": row["last_contact_at"],
        "next_follow_up_at": row["next_follow_up_at"],
        "created_at": row["created_at"]
    }


class InquiryCreate(BaseModel):
    customer_name: str
    phone: str | None = None
    destination: str | None = None
    people_count: int | None = None
    budget: int | None = None
    departure_date: str | None = None
    message: str
    source: str = "未知"
    assigned_sales: str = "未分配"
    priority: Priority = "medium"
    last_contact_at: datetime | None = None
    next_follow_up_at: datetime | None = None


@router.post("/inquiries")
def create_inquiry(inquiry: InquiryCreate):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO inquiries
    (
        customer_name, phone, destination, people_count, budget,
        departure_date, message, source, assigned_sales, priority,
        last_contact_at, next_follow_up_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        inquiry.customer_name,
        inquiry.phone,
        inquiry.destination,
        inquiry.people_count,
        inquiry.budget,
        inquiry.departure_date,
        inquiry.message,
        inquiry.source,
        inquiry.assigned_sales,
        inquiry.priority,
        format_datetime(inquiry.last_contact_at),
        format_datetime(inquiry.next_follow_up_at)
    ))

    conn.commit()
    inquiry_id = cursor.lastrowid
    conn.close()

    return {
        "success": True,
        "message": "客户咨询记录创建成功",
        "inquiry_id": inquiry_id
    }


@router.get("/inquiries")
def get_inquiries(
    follow_status: str | None = None,
    assigned_sales: str | None = None,
    priority: Priority | None = None,
    source: str | None = None,
    next_follow_up_before: datetime | None = None,
):
    conn = get_connection()
    cursor = conn.cursor()

    sql = f"""
    SELECT {INQUIRY_SELECT_FIELDS}
    FROM inquiries
    """

    conditions = []
    params = []

    if follow_status:
        conditions.append("follow_status = ?")
        params.append(follow_status)

    if assigned_sales:
        conditions.append("assigned_sales = ?")
        params.append(assigned_sales)

    if priority:
        conditions.append("priority = ?")
        params.append(priority)

    if source:
        conditions.append("source = ?")
        params.append(source)

    if next_follow_up_before:
        conditions.append("next_follow_up_at IS NOT NULL AND next_follow_up_at <= ?")
        params.append(format_datetime(next_follow_up_before))

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY id DESC"

    cursor.execute(sql, params)

    rows = cursor.fetchall()
    conn.close()

    inquiries = [serialize_inquiry(row) for row in rows]

    return {
        "success": True,
        "count": len(inquiries),
        "inquiries": inquiries
    }


@router.get("/inquiries/follow-up/today")
def get_today_follow_up_inquiries():
    conn = get_connection()
    cursor = conn.cursor()
    current_time = datetime.now().isoformat(timespec="seconds")

    cursor.execute(f"""
    SELECT {INQUIRY_SELECT_FIELDS}
    FROM inquiries
    WHERE next_follow_up_at IS NOT NULL
      AND next_follow_up_at <= ?
    ORDER BY next_follow_up_at ASC, id DESC
    """, (current_time,))

    rows = cursor.fetchall()
    conn.close()

    inquiries = [serialize_inquiry(row) for row in rows]

    return {
        "success": True,
        "count": len(inquiries),
        "inquiries": inquiries
    }


@router.get("/inquiries/{inquiry_id}")
def get_inquiry_detail(inquiry_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
    SELECT {INQUIRY_SELECT_FIELDS}
    FROM inquiries
    WHERE id = ?
    """, (inquiry_id,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="未找到该客户咨询记录")

    return {
        "success": True,
        "inquiry": serialize_inquiry(row)
    }


class InquiryStatusUpdate(BaseModel):
    follow_status: str


@router.patch("/inquiries/{inquiry_id}/status")
def update_inquiry_status(inquiry_id: int, status_update: InquiryStatusUpdate):
    if status_update.follow_status not in ALLOWED_STATUSES:
        return {
            "success": False,
            "message": "无效的跟进状态",
            "allowed_statuses": ALLOWED_STATUSES
        }

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, customer_name, follow_status
    FROM inquiries
    WHERE id = ?
    """, (inquiry_id,))

    inquiry = cursor.fetchone()

    if inquiry is None:
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该客户咨询记录")

    cursor.execute("""
    UPDATE inquiries
    SET follow_status = ?
    WHERE id = ?
    """, (status_update.follow_status, inquiry_id))

    conn.commit()

    cursor.execute(f"""
    SELECT {INQUIRY_SELECT_FIELDS}
    FROM inquiries
    WHERE id = ?
    """, (inquiry_id,))

    updated = cursor.fetchone()
    conn.close()

    return {
        "success": True,
        "message": "客户跟进状态更新成功",
        "inquiry": serialize_inquiry(updated)
    }
