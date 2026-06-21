from fastapi import HTTPException


class OrderStateMachine:
    """订单状态的唯一写入口。"""

    TRANSITIONS = {
        "draft": {"pending_payment", "cancelled"},
        "pending_payment": {"paid", "cancelled"},
        "paid": {"fulfilling"},
        "fulfilling": {"completed"},
        "completed": set(),
        "cancelled": set(),
    }

    def __init__(self, cursor, now_factory):
        self.cursor = cursor
        self.now_factory = now_factory

    def transition(self, order, target_status):
        current_status = order["order_status"]
        if current_status == target_status:
            return order
        if target_status not in self.TRANSITIONS.get(current_status, set()):
            raise HTTPException(status_code=400, detail="不允许的订单状态流转")
        if target_status == "paid" and order["payment_status"] != "mock_paid":
            raise HTTPException(status_code=400, detail="订单未完成模拟支付")
        if target_status == "cancelled" and order["payment_status"] != "unpaid":
            raise HTTPException(status_code=400, detail="已支付订单不能取消")

        fulfillment_status = order["fulfillment_status"]
        if target_status == "fulfilling":
            fulfillment_status = "in_progress"
        elif target_status == "completed":
            fulfillment_status = "completed"

        self.cursor.execute(
            """
            UPDATE orders
            SET order_status = ?, fulfillment_status = ?, updated_at = ?
            WHERE id = ? AND order_status = ?
            """,
            (
                target_status,
                fulfillment_status,
                self.now_factory(),
                order["id"],
                current_status,
            ),
        )
        if self.cursor.rowcount != 1:
            raise HTTPException(status_code=409, detail="订单状态已被并发修改")
        self.cursor.execute("SELECT * FROM orders WHERE id = ?", (order["id"],))
        return self.cursor.fetchone()
