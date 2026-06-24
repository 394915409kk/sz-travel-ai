from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apps.backend.db import get_connection
from apps.backend.security import require_internal_api_key

router = APIRouter()

TaskStatus = Literal["pending", "done", "cancelled"]
Priority = Literal["high", "medium", "low"]

TASK_SELECT_FIELDS = """
t.id, t.inquiry_id, t.assigned_sales, t.task_title, t.task_status,
t.priority, t.due_at, t.completed_at, t.created_at,
i.customer_name, i.phone, i.destination, i.follow_status
"""


class FollowUpTaskStatusUpdate(BaseModel):
    task_status: TaskStatus


def format_datetime(value: datetime | None):
    if value is None:
        return None
    return value.isoformat(timespec="seconds")


def serialize_task(row):
    return {
        "id": row["id"],
        "inquiry_id": row["inquiry_id"],
        "assigned_sales": row["assigned_sales"],
        "task_title": row["task_title"],
        "task_status": row["task_status"],
        "priority": row["priority"],
        "due_at": row["due_at"],
        "completed_at": row["completed_at"],
        "created_at": row["created_at"],
        "inquiry": {
            "customer_name": row["customer_name"],
            "phone": row["phone"],
            "destination": row["destination"],
            "follow_status": row["follow_status"],
        },
    }


def fetch_task(cursor, task_id):
    cursor.execute(f"""
    SELECT {TASK_SELECT_FIELDS}
    FROM follow_up_tasks AS t
    JOIN inquiries AS i ON i.id = t.inquiry_id
    WHERE t.id = ?
    """, (task_id,))
    return cursor.fetchone()


@router.post("/follow-up-tasks/generate")
def generate_follow_up_tasks(_: None = Depends(require_internal_api_key)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        i.id AS inquiry_id,
        i.customer_name,
        i.destination,
        i.assigned_sales,
        i.priority,
        i.next_follow_up_at
    FROM inquiries AS i
    WHERE i.next_follow_up_at IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM follow_up_tasks AS t
          WHERE t.inquiry_id = i.id
            AND t.task_status IN ('pending', 'done')
      )
    ORDER BY i.next_follow_up_at ASC, i.id ASC
    """)
    inquiries = cursor.fetchall()

    generated_ids = []
    for inquiry in inquiries:
        task_title = f"跟进客户 {inquiry['customer_name']}"
        if inquiry["destination"]:
            task_title += f" - {inquiry['destination']}"

        cursor.execute("""
        INSERT OR IGNORE INTO follow_up_tasks
        (
            inquiry_id, assigned_sales, task_title, task_status,
            priority, due_at
        )
        VALUES (?, ?, ?, 'pending', ?, ?)
        """, (
            inquiry["inquiry_id"],
            inquiry["assigned_sales"],
            task_title,
            inquiry["priority"],
            inquiry["next_follow_up_at"],
        ))

        if cursor.rowcount == 1:
            generated_ids.append(cursor.lastrowid)

    conn.commit()

    tasks = []
    if generated_ids:
        placeholders = ", ".join("?" for _ in generated_ids)
        cursor.execute(f"""
        SELECT {TASK_SELECT_FIELDS}
        FROM follow_up_tasks AS t
        JOIN inquiries AS i ON i.id = t.inquiry_id
        WHERE t.id IN ({placeholders})
        ORDER BY
            CASE WHEN t.due_at IS NULL THEN 1 ELSE 0 END,
            t.due_at ASC,
            t.id ASC
        """, generated_ids)
        tasks = [serialize_task(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "success": True,
        "generated_count": len(tasks),
        "tasks": tasks,
    }


@router.get("/follow-up-tasks")
def get_follow_up_tasks(
    assigned_sales: str | None = None,
    task_status: TaskStatus | None = None,
    priority: Priority | None = None,
    due_before: datetime | None = None,
):
    conn = get_connection()
    cursor = conn.cursor()

    sql = f"""
    SELECT {TASK_SELECT_FIELDS}
    FROM follow_up_tasks AS t
    JOIN inquiries AS i ON i.id = t.inquiry_id
    """
    conditions = []
    params = []

    if assigned_sales:
        conditions.append("t.assigned_sales = ?")
        params.append(assigned_sales)

    if task_status:
        conditions.append("t.task_status = ?")
        params.append(task_status)

    if priority:
        conditions.append("t.priority = ?")
        params.append(priority)

    if due_before:
        conditions.append("t.due_at IS NOT NULL AND t.due_at <= ?")
        params.append(format_datetime(due_before))

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += """
    ORDER BY
        CASE WHEN t.due_at IS NULL THEN 1 ELSE 0 END,
        t.due_at ASC,
        t.id ASC
    """

    cursor.execute(sql, params)
    tasks = [serialize_task(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "success": True,
        "count": len(tasks),
        "tasks": tasks,
    }


@router.get("/follow-up-tasks/today")
def get_today_follow_up_tasks():
    conn = get_connection()
    cursor = conn.cursor()
    current_time = datetime.now().isoformat(timespec="seconds")

    cursor.execute(f"""
    SELECT {TASK_SELECT_FIELDS}
    FROM follow_up_tasks AS t
    JOIN inquiries AS i ON i.id = t.inquiry_id
    WHERE t.task_status = 'pending'
      AND t.due_at IS NOT NULL
      AND t.due_at <= ?
    ORDER BY t.due_at ASC, t.id ASC
    """, (current_time,))

    tasks = [serialize_task(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "success": True,
        "count": len(tasks),
        "tasks": tasks,
    }


@router.get("/follow-up-tasks/{task_id}")
def get_follow_up_task_detail(task_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    task = fetch_task(cursor, task_id)
    conn.close()

    if task is None:
        raise HTTPException(status_code=404, detail="未找到该销售跟进任务")

    return {
        "success": True,
        "task": serialize_task(task),
    }


@router.patch("/follow-up-tasks/{task_id}/status")
def update_follow_up_task_status(
    task_id: int,
    status_update: FollowUpTaskStatusUpdate,
    _: None = Depends(require_internal_api_key),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, task_status, completed_at
    FROM follow_up_tasks
    WHERE id = ?
    """, (task_id,))
    existing_task = cursor.fetchone()

    if existing_task is None:
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该销售跟进任务")

    completed_at = None
    if status_update.task_status == "done":
        completed_at = (
            existing_task["completed_at"]
            or datetime.now().isoformat(timespec="seconds")
        )

    cursor.execute("""
    UPDATE follow_up_tasks
    SET task_status = ?, completed_at = ?
    WHERE id = ?
    """, (status_update.task_status, completed_at, task_id))
    conn.commit()

    updated_task = fetch_task(cursor, task_id)
    conn.close()

    return {
        "success": True,
        "message": "销售跟进任务状态更新成功",
        "task": serialize_task(updated_task),
    }
