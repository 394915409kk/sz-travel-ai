from apps.backend.services.inventory_service import RESOURCE_TABLES


HIGH_MARGIN_THRESHOLD = 0.30
HIGH_PROFIT_THRESHOLD = 1000.0
LOW_MARGIN_THRESHOLD = 0.10


class ProfitService:
    """基于订单、保险和资源成本实时计算经营利润。"""

    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()

    def get_order_profit(self, order_id):
        self.cursor.execute(
            """
            SELECT o.*, i.assigned_sales AS sales
            FROM orders AS o
            LEFT JOIN inquiries AS i ON i.id = o.inquiry_id
            WHERE o.id = ?
            """,
            (order_id,),
        )
        order = self.cursor.fetchone()
        if order is None:
            return None
        return self._calculate_order_profit(order)

    def list_order_profits(
        self,
        destination=None,
        date_from=None,
        date_to=None,
        sales=None,
        order_status=None,
        payment_status=None,
    ):
        conditions = []
        params = []
        for column, value in (
            ("o.destination", destination),
            ("i.assigned_sales", sales),
            ("o.order_status", order_status),
            ("o.payment_status", payment_status),
        ):
            if value is not None:
                conditions.append(f"{column} = ?")
                params.append(value)
        if date_from is not None:
            conditions.append("date(o.created_at) >= date(?)")
            params.append(str(date_from))
        if date_to is not None:
            conditions.append("date(o.created_at) <= date(?)")
            params.append(str(date_to))

        sql = """
            SELECT o.*, i.assigned_sales AS sales
            FROM orders AS o
            LEFT JOIN inquiries AS i ON i.id = o.inquiry_id
        """
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY o.id DESC"

        self.cursor.execute(sql, params)
        return [self._calculate_order_profit(order) for order in self.cursor.fetchall()]

    def get_summary(self, **filters):
        return self.summarize_orders(self.list_order_profits(**filters))

    @staticmethod
    def summarize_orders(orders):
        total_revenue = round(sum(order["order_revenue"] for order in orders), 2)
        total_resource_cost = round(
            sum(order["resource_cost"] for order in orders),
            2,
        )
        total_insurance_revenue = round(
            sum(order["insurance_revenue"] for order in orders),
            2,
        )
        total_gross_profit = round(
            sum(order["gross_profit"] for order in orders),
            2,
        )
        average_margin = (
            round(total_gross_profit / total_revenue, 4)
            if total_revenue > 0
            else 0.0
        )
        return {
            "total_orders": len(orders),
            "paid_orders": sum(
                order["payment_status"] == "mock_paid" for order in orders
            ),
            "cancelled_orders": sum(
                order["order_status"] == "cancelled" for order in orders
            ),
            "total_revenue": total_revenue,
            "total_resource_cost": total_resource_cost,
            "total_insurance_revenue": total_insurance_revenue,
            "total_gross_profit": total_gross_profit,
            "average_margin": average_margin,
            "high_profit_orders": sum(
                order["profit_level"] == "high_profit" for order in orders
            ),
            "low_profit_orders": sum(
                order["profit_level"] == "low_profit" for order in orders
            ),
            "loss_orders": sum(
                order["profit_level"] == "loss" for order in orders
            ),
        }

    def _calculate_order_profit(self, order):
        self.cursor.execute(
            """
            SELECT resource_type, resource_id, quantity
            FROM order_items
            WHERE order_id = ?
            ORDER BY id ASC
            """,
            (order["id"],),
        )
        items = self.cursor.fetchall()
        missing_resource_cost = len(items) == 0
        resource_cost = 0.0
        for item in items:
            table_name = RESOURCE_TABLES.get(item["resource_type"])
            if table_name is None:
                missing_resource_cost = True
                continue
            self.cursor.execute(
                f"SELECT cost_price FROM {table_name} WHERE id = ?",
                (item["resource_id"],),
            )
            resource = self.cursor.fetchone()
            if resource is None or resource["cost_price"] is None:
                missing_resource_cost = True
                continue
            resource_cost += float(resource["cost_price"]) * item["quantity"]

        self.cursor.execute(
            """
            SELECT COALESCE(SUM(price), 0) AS insurance_revenue
            FROM order_insurances
            WHERE order_id = ?
            """,
            (order["id"],),
        )
        insurance_revenue = float(self.cursor.fetchone()["insurance_revenue"])

        order_revenue = round(float(order["total_amount"]), 2)
        resource_cost = round(resource_cost, 2)
        insurance_revenue = round(insurance_revenue, 2)
        gross_profit = round(order_revenue - resource_cost, 2)
        gross_margin = (
            round(gross_profit / order_revenue, 4)
            if order_revenue > 0
            else 0.0
        )
        profit_level = self._profit_level(
            order_revenue,
            gross_profit,
            gross_margin,
        )
        risk_flags = self._risk_flags(
            order,
            order_revenue,
            gross_profit,
            gross_margin,
            missing_resource_cost,
        )

        return {
            "order_id": order["id"],
            "order_no": order["order_no"],
            "customer_name": order["customer_name"],
            "destination": order["destination"],
            "sales": order["sales"],
            "order_status": order["order_status"],
            "payment_status": order["payment_status"],
            "created_at": order["created_at"],
            "order_revenue": order_revenue,
            "resource_cost": resource_cost,
            "insurance_revenue": insurance_revenue,
            "gross_profit": gross_profit,
            "gross_margin": gross_margin,
            "profit_level": profit_level,
            "risk_flags": risk_flags,
            "recommendation": self._recommendation(profit_level, risk_flags),
        }

    @staticmethod
    def _profit_level(order_revenue, gross_profit, gross_margin):
        if gross_profit < 0:
            return "loss"
        if (
            gross_margin >= HIGH_MARGIN_THRESHOLD
            or gross_profit >= HIGH_PROFIT_THRESHOLD
        ):
            return "high_profit"
        if order_revenue <= 0 or gross_margin < LOW_MARGIN_THRESHOLD:
            return "low_profit"
        return "normal_profit"

    @staticmethod
    def _risk_flags(
        order,
        order_revenue,
        gross_profit,
        gross_margin,
        missing_resource_cost,
    ):
        flags = []
        if gross_profit < 0:
            flags.append("negative_profit")
        if order_revenue <= 0 or gross_margin < LOW_MARGIN_THRESHOLD:
            flags.append("low_margin")
        if missing_resource_cost:
            flags.append("missing_resource_cost")
        if order["payment_status"] == "unpaid":
            flags.append("unpaid_order")
        if order["order_status"] == "cancelled":
            flags.append("cancelled_order")
        return flags

    @staticmethod
    def _recommendation(profit_level, risk_flags):
        suggestions = []
        if "cancelled_order" in risk_flags:
            suggestions.append("核对取消原因、退款记录和库存释放状态")
        if "unpaid_order" in risk_flags:
            suggestions.append("尽快跟进客户付款或关闭无效订单")
        if "missing_resource_cost" in risk_flags:
            suggestions.append("补齐订单资源和成本价后再确认利润")
        if "negative_profit" in risk_flags:
            suggestions.append("立即复核报价、资源采购价和优惠政策")
        elif "low_margin" in risk_flags:
            suggestions.append("提高报价或优化资源组合以改善毛利率")
        elif profit_level == "high_profit":
            suggestions.append("优先复用并推广该订单对应产品组合")
        else:
            suggestions.append("维持当前报价并持续跟踪成本变化")
        return "；".join(suggestions)
