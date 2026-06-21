import json
import sqlite3

from fastapi import HTTPException


class PaymentIdempotencyGuard:
    """用唯一支付事件记录保证同一事件只处理一次。"""

    def __init__(self, cursor, now_factory):
        self.cursor = cursor
        self.now_factory = now_factory

    def get_processed_result(self, payment_event_id, order_id):
        self.cursor.execute(
            """
            SELECT order_id, event_status, response_json
            FROM payment_events
            WHERE payment_event_id = ?
            """,
            (payment_event_id,),
        )
        event = self.cursor.fetchone()
        if event is None:
            return None
        if event["order_id"] != order_id:
            raise HTTPException(status_code=409, detail="支付事件已用于其他订单")
        if event["event_status"] != "processed" or not event["response_json"]:
            raise HTTPException(status_code=409, detail="支付事件正在处理中")
        return json.loads(event["response_json"])

    def claim(self, payment_event_id, order_id):
        try:
            self.cursor.execute(
                """
                INSERT INTO payment_events
                (payment_event_id, order_id, event_status, created_at)
                VALUES (?, ?, 'processing', ?)
                """,
                (payment_event_id, order_id, self.now_factory()),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="支付事件已被占用") from error

    def complete(self, payment_event_id, result):
        self.cursor.execute(
            """
            UPDATE payment_events
            SET event_status = 'processed', response_json = ?, processed_at = ?
            WHERE payment_event_id = ? AND event_status = 'processing'
            """,
            (
                json.dumps(result, ensure_ascii=False, sort_keys=True),
                self.now_factory(),
                payment_event_id,
            ),
        )
        if self.cursor.rowcount != 1:
            raise HTTPException(status_code=409, detail="支付事件完成状态异常")
