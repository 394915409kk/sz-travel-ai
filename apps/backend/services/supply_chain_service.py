import json
from collections import defaultdict
from datetime import datetime

from fastapi import HTTPException

from apps.backend.db import get_connection
from apps.backend.services.inventory_service import RESOURCE_TABLES


class SupplyChainService:
    """基于本地资源、库存和订单明细生成供应商表现与采购建议。"""

    @classmethod
    def analyze(cls):
        conn = get_connection()
        cursor = conn.cursor()
        groups = defaultdict(lambda: {
            "resource_ids": [], "stockout_count": 0, "slow_count": 0,
            "stock_quantity": 0, "sold_quantity": 0, "reserved_quantity": 0,
        })
        reverse_tables = {table: resource_type for resource_type, table in RESOURCE_TABLES.items()}
        for table, resource_type in reverse_tables.items():
            cursor.execute(f"SELECT id, supplier_name, destination, stock_quantity, sold_quantity, reserved_quantity FROM {table}")
            for row in cursor.fetchall():
                key = (row["supplier_name"], resource_type, row["destination"])
                group = groups[key]
                group["resource_ids"].append(row["id"])
                available = row["stock_quantity"] - row["sold_quantity"] - row["reserved_quantity"]
                group["stockout_count"] += available <= 0
                group["slow_count"] += row["stock_quantity"] > 0 and row["sold_quantity"] == 0 and row["reserved_quantity"] == 0
                group["stock_quantity"] += row["stock_quantity"]
                group["sold_quantity"] += row["sold_quantity"]
                group["reserved_quantity"] += row["reserved_quantity"]

        performance_ids = []
        suggestion_ids = []
        now = datetime.now().isoformat(timespec="seconds")
        for (supplier, resource_type, destination), inventory in groups.items():
            table = RESOURCE_TABLES[resource_type]
            placeholders = ",".join("?" for _ in inventory["resource_ids"])
            cursor.execute(
                f"""
                SELECT COUNT(DISTINCT oi.order_id) AS total_orders,
                       COALESCE(SUM(oi.total_price), 0) AS revenue,
                       COALESCE(SUM(oi.quantity * r.cost_price), 0) AS cost,
                       COUNT(DISTINCT CASE WHEN o.order_status = 'cancelled' THEN o.id END) AS cancellations
                FROM order_items AS oi
                JOIN orders AS o ON o.id = oi.order_id
                JOIN {table} AS r ON r.id = oi.resource_id
                WHERE oi.resource_type = ? AND oi.resource_id IN ({placeholders})
                """,
                (resource_type, *inventory["resource_ids"]),
            )
            order_data = cursor.fetchone()
            revenue = round(float(order_data["revenue"]), 2)
            cost = round(float(order_data["cost"]), 2)
            profit = round(revenue - cost, 2)
            margin = round(profit / revenue, 4) if revenue > 0 else 0.0
            cancellations = order_data["cancellations"]
            risks = []
            if inventory["stockout_count"]:
                risks.append("STOCK_SHORTAGE_RISK")
            if cancellations:
                risks.append("SUPPLIER_RISK")
            if revenue > 0 and margin < 0.10:
                risks.append("LOW_MARGIN_RISK")
            score = 100
            score -= min(35, inventory["stockout_count"] * 15)
            score -= min(30, cancellations * 10)
            if revenue > 0:
                score += min(10, max(-20, margin * 30))
            score = round(max(0, min(100, score)), 2)
            recommendation = cls._recommendation(risks, inventory["slow_count"])
            cursor.execute(
                """
                INSERT INTO supplier_performance (
                    supplier_name, resource_type, destination, total_resources,
                    total_orders, total_revenue, total_cost, total_profit,
                    average_margin, stockout_count, cancellation_count,
                    performance_score, risk_flags_json, recommendation_text,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(supplier_name, resource_type, destination) DO UPDATE SET
                    total_resources = excluded.total_resources,
                    total_orders = excluded.total_orders,
                    total_revenue = excluded.total_revenue,
                    total_cost = excluded.total_cost,
                    total_profit = excluded.total_profit,
                    average_margin = excluded.average_margin,
                    stockout_count = excluded.stockout_count,
                    cancellation_count = excluded.cancellation_count,
                    performance_score = excluded.performance_score,
                    risk_flags_json = excluded.risk_flags_json,
                    recommendation_text = excluded.recommendation_text,
                    updated_at = excluded.updated_at
                """,
                (supplier, resource_type, destination, len(inventory["resource_ids"]),
                 order_data["total_orders"], revenue, cost, profit, margin,
                 inventory["stockout_count"], cancellations, score,
                 json.dumps(risks, ensure_ascii=False), recommendation, now),
            )
            cursor.execute("SELECT id FROM supplier_performance WHERE supplier_name = ? AND resource_type = ? AND destination = ?", (supplier, resource_type, destination))
            performance_ids.append(cursor.fetchone()["id"])
            suggestions = cls._suggestions(inventory, margin, revenue, cancellations)
            for action, quantity, reason, priority in suggestions:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO procurement_suggestions (
                        supplier_name, resource_type, destination, suggested_action,
                        suggested_quantity, reason, priority
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (supplier, resource_type, destination, action, quantity, reason, priority),
                )
                if cursor.rowcount:
                    suggestion_ids.append(cursor.lastrowid)
        conn.commit()
        performances = cls._list_performances(cursor)
        suggestions = cls._list_suggestions(cursor)
        conn.close()
        return {"suppliers": performances, "procurement_suggestions": suggestions, "generated_suggestion_count": len(suggestion_ids)}

    @staticmethod
    def _recommendation(risks, slow_count):
        if "STOCK_SHORTAGE_RISK" in risks:
            return "核对未来订单需求后补充库存，补货前不得承诺可售。"
        if "SUPPLIER_RISK" in risks:
            return "复盘取消原因和服务条款，必要时准备替代供应商。"
        if slow_count:
            return "存在无销售占用库存，建议降低采购或调整产品组合。"
        return "当前按规则继续监控价格、库存和履约表现。"

    @staticmethod
    def _suggestions(inventory, margin, revenue, cancellations):
        result = []
        if inventory["stockout_count"]:
            quantity = max(1, inventory["sold_quantity"] + inventory["reserved_quantity"])
            result.append(("increase_stock", quantity, "存在可用库存为零的资源", "high"))
        if inventory["slow_count"]:
            result.append(("reduce_stock", inventory["stock_quantity"], "资源有库存但尚无销售或预留", "medium"))
        if revenue > 0 and margin < 0.10:
            result.append(("renegotiate_price", 0, "历史订单毛利率低于 10%", "high"))
        if cancellations >= 3:
            result.append(("replace_supplier", 0, "供应商关联取消订单达到 3 单", "high"))
        elif not result:
            result.append(("keep_monitoring", 0, "暂无明确补货、减量或替换信号", "low"))
        return result

    @staticmethod
    def _serialize_performance(row):
        item = dict(row)
        try:
            flags = json.loads(item.pop("risk_flags_json") or "[]")
            item["risk_flags"] = flags if isinstance(flags, list) else []
        except json.JSONDecodeError:
            item["risk_flags"] = []
        return item

    @classmethod
    def _list_performances(cls, cursor, supplier_name=None, risks_only=False):
        sql = "SELECT * FROM supplier_performance"
        conditions = []
        params = []
        if supplier_name:
            conditions.append("supplier_name = ?")
            params.append(supplier_name)
        if risks_only:
            conditions.append("risk_flags_json <> '[]'")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY performance_score ASC, id DESC"
        cursor.execute(sql, params)
        return [cls._serialize_performance(row) for row in cursor.fetchall()]

    @staticmethod
    def _list_suggestions(cursor, status=None):
        sql = "SELECT * FROM procurement_suggestions"
        params = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id DESC"
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def list_suppliers(cls, supplier_name=None, risks_only=False):
        conn = get_connection()
        cursor = conn.cursor()
        rows = cls._list_performances(cursor, supplier_name, risks_only)
        conn.close()
        if supplier_name and not rows:
            raise HTTPException(status_code=404, detail="未找到该供应商分析")
        return rows

    @classmethod
    def list_suggestions(cls, status=None):
        conn = get_connection()
        cursor = conn.cursor()
        rows = cls._list_suggestions(cursor, status)
        conn.close()
        return rows

    @classmethod
    def update_suggestion_status(cls, suggestion_id, status):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM procurement_suggestions WHERE id = ?", (suggestion_id,))
        if cursor.fetchone() is None:
            conn.close()
            raise HTTPException(status_code=404, detail="未找到该采购建议")
        cursor.execute("UPDATE procurement_suggestions SET status = ?, updated_at = ? WHERE id = ?", (status, datetime.now().isoformat(timespec="seconds"), suggestion_id))
        conn.commit()
        cursor.execute("SELECT * FROM procurement_suggestions WHERE id = ?", (suggestion_id,))
        row = dict(cursor.fetchone())
        conn.close()
        return row

    @classmethod
    def slow_moving_resources(cls):
        conn = get_connection()
        cursor = conn.cursor()
        resources = []
        for resource_type, table in RESOURCE_TABLES.items():
            cursor.execute(
                f"""
                SELECT id, supplier_name, destination, resource_name,
                       stock_quantity, sold_quantity, reserved_quantity
                FROM {table}
                WHERE status = 'active' AND stock_quantity > 0
                  AND sold_quantity = 0 AND reserved_quantity = 0
                """
            )
            for row in cursor.fetchall():
                resources.append({"resource_type": resource_type, **dict(row), "risk_flag": "SUPPLIER_RISK"})
        conn.close()
        return resources
