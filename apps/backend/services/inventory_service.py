from fastapi import HTTPException


RESOURCE_TABLES = {
    "transport": "travel_transport_resources",
    "hotel_room": "hotel_room_resources",
    "attraction_ticket": "attraction_ticket_resources",
    "restaurant_meal": "restaurant_meal_resources",
    "activity": "activity_resources",
}


class InventoryConsistencyService:
    """订单库存的唯一写入口，调用方必须处于数据库事务中。"""

    def __init__(self, cursor, resource_type=None):
        self.cursor = cursor
        self.resource_type = resource_type

    def _table_name(self):
        if self.resource_type not in RESOURCE_TABLES:
            raise HTTPException(status_code=400, detail="不支持的资源类型")
        return RESOURCE_TABLES[self.resource_type]

    def validate_stock(self, resource_id, qty):
        if qty <= 0:
            raise HTTPException(status_code=400, detail="库存数量必须大于 0")
        table_name = self._table_name()
        self.cursor.execute(
            f"""
            SELECT id, sale_price, stock_quantity, sold_quantity,
                   reserved_quantity, status
            FROM {table_name}
            WHERE id = ?
            """,
            (resource_id,),
        )
        resource = self.cursor.fetchone()
        if resource is None:
            raise HTTPException(status_code=404, detail="未找到订单资源")
        if resource["status"] != "active":
            raise HTTPException(status_code=400, detail="订单资源未启用")

        available = (
            resource["stock_quantity"]
            - resource["sold_quantity"]
            - resource["reserved_quantity"]
        )
        if available < qty:
            raise HTTPException(status_code=400, detail="库存不足")
        return resource

    def lock_stock(self, order_id, resource_id, qty):
        self.cursor.execute("SELECT id FROM orders WHERE id = ?", (order_id,))
        if self.cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="未找到该订单")

        resource = self.validate_stock(resource_id, qty)
        table_name = self._table_name()
        self.cursor.execute(
            f"""
            UPDATE {table_name}
            SET reserved_quantity = reserved_quantity + ?
            WHERE id = ?
              AND stock_quantity - sold_quantity - reserved_quantity >= ?
            """,
            (qty, resource_id, qty),
        )
        if self.cursor.rowcount != 1:
            raise HTTPException(status_code=409, detail="库存并发锁定失败")
        return resource

    def release_stock(self, order_id):
        order = self._fetch_order_payment_status(order_id)
        if order["payment_status"] != "unpaid":
            raise HTTPException(status_code=400, detail="已支付订单不能释放库存")

        for item in self._fetch_order_items(order_id):
            table_name = RESOURCE_TABLES[item["resource_type"]]
            self.cursor.execute(
                f"""
                UPDATE {table_name}
                SET reserved_quantity = reserved_quantity - ?
                WHERE id = ?
                  AND reserved_quantity >= ?
                  AND sold_quantity >= 0
                  AND stock_quantity >= sold_quantity + reserved_quantity
                """,
                (item["quantity"], item["resource_id"], item["quantity"]),
            )
            if self.cursor.rowcount != 1:
                raise HTTPException(status_code=409, detail="订单预留库存状态异常")

    def commit_sale(self, order_id):
        order = self._fetch_order_payment_status(order_id)
        if order["payment_status"] == "mock_paid":
            return False
        if order["payment_status"] != "unpaid":
            raise HTTPException(status_code=400, detail="当前支付状态不能提交库存销售")

        for item in self._fetch_order_items(order_id):
            table_name = RESOURCE_TABLES[item["resource_type"]]
            self.cursor.execute(
                f"""
                UPDATE {table_name}
                SET reserved_quantity = reserved_quantity - ?,
                    sold_quantity = sold_quantity + ?
                WHERE id = ?
                  AND reserved_quantity >= ?
                  AND sold_quantity >= 0
                  AND stock_quantity >= sold_quantity + reserved_quantity
                """,
                (
                    item["quantity"],
                    item["quantity"],
                    item["resource_id"],
                    item["quantity"],
                ),
            )
            if self.cursor.rowcount != 1:
                raise HTTPException(status_code=409, detail="订单预留库存状态异常")
        return True

    def _fetch_order_payment_status(self, order_id):
        self.cursor.execute(
            "SELECT id, payment_status FROM orders WHERE id = ?",
            (order_id,),
        )
        order = self.cursor.fetchone()
        if order is None:
            raise HTTPException(status_code=404, detail="未找到该订单")
        return order

    def _fetch_order_items(self, order_id):
        self.cursor.execute(
            """
            SELECT resource_type, resource_id, quantity
            FROM order_items
            WHERE order_id = ?
            ORDER BY id ASC
            """,
            (order_id,),
        )
        return self.cursor.fetchall()
