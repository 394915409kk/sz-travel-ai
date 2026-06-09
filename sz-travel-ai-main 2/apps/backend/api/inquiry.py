from fastapi import APIRouter
from pydantic import BaseModel
from apps.backend.db import get_connection

router = APIRouter()


class InquiryCreate(BaseModel):
    customer_name: str
    phone: str | None = None
    destination: str | None = None
    people_count: int | None = None
    budget: int | None = None
    departure_date: str | None = None
    message: str


@router.post("/inquiries")
def create_inquiry(inquiry: InquiryCreate):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO inquiries
    (customer_name, phone, destination, people_count, budget, departure_date, message)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        inquiry.customer_name,
        inquiry.phone,
        inquiry.destination,
        inquiry.people_count,
        inquiry.budget,
        inquiry.departure_date,
        inquiry.message
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
def get_inquiries():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, customer_name, phone, destination, people_count, budget,
           departure_date, message, follow_status, created_at
    FROM inquiries
    ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    inquiries = []

    for row in rows:
        inquiries.append({
            "id": row["id"],
            "customer_name": row["customer_name"],
            "phone": row["phone"],
            "destination": row["destination"],
            "people_count": row["people_count"],
            "budget": row["budget"],
            "departure_date": row["departure_date"],
            "message": row["message"],
            "follow_status": row["follow_status"],
            "created_at": row["created_at"]
        })

    return {
        "success": True,
        "count": len(inquiries),
        "inquiries": inquiries
    }


@router.get("/inquiries/{inquiry_id}")
def get_inquiry_detail(inquiry_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, customer_name, phone, destination, people_count, budget,
           departure_date, message, follow_status, created_at
    FROM inquiries
    WHERE id = ?
    """, (inquiry_id,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return {
            "success": False,
            "message": "未找到该客户咨询记录"
        }

    return {
        "success": True,
        "inquiry": {
            "id": row["id"],
            "customer_name": row["customer_name"],
            "phone": row["phone"],
            "destination": row["destination"],
            "people_count": row["people_count"],
            "budget": row["budget"],
            "departure_date": row["departure_date"],
            "message": row["message"],
            "follow_status": row["follow_status"],
            "created_at": row["created_at"]
        }
    }


class InquiryStatusUpdate(BaseModel):
    follow_status: str


@router.patch("/inquiries/{inquiry_id}/status")
def update_inquiry_status(inquiry_id: int, status_update: InquiryStatusUpdate):
    allowed_statuses = [
        "new",
        "contacted",
        "interested",
        "quoted",
        "confirmed",
        "lost"
    ]

    if status_update.follow_status not in allowed_statuses:
        return {
            "success": False,
            "message": "无效的跟进状态",
            "allowed_statuses": allowed_statuses
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
        return {
            "success": False,
            "message": "未找到该客户咨询记录"
        }

    cursor.execute("""
    UPDATE inquiries
    SET follow_status = ?
    WHERE id = ?
    """, (status_update.follow_status, inquiry_id))

    conn.commit()

    cursor.execute("""
    SELECT id, customer_name, phone, destination, people_count, budget,
           departure_date, message, follow_status, created_at
    FROM inquiries
    WHERE id = ?
    """, (inquiry_id,))

    updated = cursor.fetchone()
    conn.close()

    return {
        "success": True,
        "message": "客户跟进状态更新成功",
        "inquiry": {
            "id": updated["id"],
            "customer_name": updated["customer_name"],
            "phone": updated["phone"],
            "destination": updated["destination"],
            "people_count": updated["people_count"],
            "budget": updated["budget"],
            "departure_date": updated["departure_date"],
            "message": updated["message"],
            "follow_status": updated["follow_status"],
            "created_at": updated["created_at"]
        }
    }
