from collections import Counter
from datetime import date

from apps.backend.db import get_connection
from apps.backend.services.ceo_agent_service import CeoAgentService
from apps.backend.services.inventory_service import RESOURCE_TABLES
from apps.backend.services.profit_service import ProfitService


class DashboardService:
    """只读汇总各业务模块，所有金额口径在返回结构中显式命名。"""

    @classmethod
    def overview(cls):
        conn = get_connection()
        cursor = conn.cursor()
        today = date.today().isoformat()
        leads = cls._count(cursor, "inquiries")
        today_leads = cls._count(cursor, "inquiries", "date(created_at) = date(?)", (today,))
        quotes = cls._count(cursor, "quotes")
        today_quotes = cls._count(cursor, "quotes", "date(created_at) = date(?)", (today,))
        orders = ProfitService(conn).list_order_profits()
        today_orders = [row for row in orders if row["created_at"][:10] == today]
        total_profit = ProfitService.summarize_orders(orders)
        today_profit = ProfitService.summarize_orders(today_orders)
        pending_followups = cls._count(cursor, "follow_up_tasks", "task_status = 'pending'")
        high_intent = cls._count(cursor, "sales_conversion_records", "conversion_stage IN ('high_intent', 'accepted') OR conversion_probability >= 0.65")
        content_pending = cls._count(cursor, "content_campaigns", "status IN ('draft', 'ready')")
        repurchase_pending = cls._count(cursor, "repurchase_tasks", "status = 'pending'")
        risk_summary = cls._risk_summary(cursor, orders)
        ceo = CeoAgentService(conn).daily_report()
        actions = cls._recommended_actions(cursor, ceo)
        result = {
            "report_date": today,
            "leads_summary": {"today": today_leads, "total": leads},
            "quote_summary": {"today": today_quotes, "total": quotes},
            "order_summary": {"today": len(today_orders), "total": len(orders), "paid": total_profit["paid_orders"]},
            "revenue_summary": {"today_sales": today_profit["total_revenue"], "total_sales": total_profit["total_revenue"]},
            "profit_summary": {"today_gross_profit": today_profit["total_gross_profit"], "today_gross_margin": today_profit["average_margin"], "total_gross_profit": total_profit["total_gross_profit"], "total_gross_margin": total_profit["average_margin"]},
            "task_summary": {"pending_follow_up": pending_followups, "high_intent": high_intent},
            "risk_summary": risk_summary,
            "content_summary": {"pending_tasks": content_pending},
            "repurchase_summary": {"pending_opportunities": repurchase_pending},
            "ceo_summary": {"key_findings": ceo["key_findings"], "risk_summary": ceo["risk_summary"], "action_suggestions": ceo["action_suggestions"]},
            "recommended_actions": actions,
        }
        conn.close()
        return result

    @staticmethod
    def _count(cursor, table, condition=None, params=()):
        sql = f"SELECT COUNT(*) AS count FROM {table}"
        if condition:
            sql += " WHERE " + condition
        cursor.execute(sql, params)
        return cursor.fetchone()["count"]

    @classmethod
    def _risk_summary(cls, cursor, orders):
        order_risks = [row for row in orders if row["risk_flags"]]
        low_margin_orders = [row for row in orders if row["profit_level"] in ("low_profit", "loss")]
        inventory_risks = 0
        for table in RESOURCE_TABLES.values():
            cursor.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE status = 'active' AND stock_quantity - sold_quantity - reserved_quantity <= 0")
            inventory_risks += cursor.fetchone()["count"]
        supplier_risks = cls._count(cursor, "supplier_performance", "risk_flags_json <> '[]'")
        finance_risks = cls._count(
            cursor,
            "finance_records",
            "status IN ('overdue', 'disputed') OR risk_flags_json <> '[]' OR (status = 'pending' AND due_date IS NOT NULL AND date(due_date) < date('now', 'localtime'))",
        )
        return {
            "risk_orders": len(order_risks), "low_margin_orders": len(low_margin_orders),
            "inventory_risks": inventory_risks, "supplier_risks": supplier_risks,
            "finance_risks": finance_risks,
        }

    @staticmethod
    def _recommended_actions(cursor, ceo):
        actions = []
        cursor.execute("SELECT next_best_action FROM sales_conversion_records WHERE conversion_stage NOT IN ('lost', 'converted') ORDER BY conversion_probability DESC LIMIT 5")
        actions.extend(row["next_best_action"] for row in cursor.fetchall())
        cursor.execute("SELECT reason FROM repurchase_tasks WHERE status = 'pending' ORDER BY CASE priority WHEN 'high' THEN 0 ELSE 1 END LIMIT 3")
        actions.extend(f"复购：{row['reason']}" for row in cursor.fetchall())
        cursor.execute("SELECT reason FROM procurement_suggestions WHERE status = 'pending' ORDER BY CASE priority WHEN 'high' THEN 0 ELSE 1 END LIMIT 3")
        actions.extend(f"采购：{row['reason']}" for row in cursor.fetchall())
        actions.extend(ceo["action_suggestions"])
        if not actions:
            actions.append("继续录入真实业务数据并复核报价、库存、利润和待办。")
        return list(dict.fromkeys(actions))

    @classmethod
    def today(cls):
        overview = cls.overview()
        return {
            "report_date": overview["report_date"],
            "today_leads": overview["leads_summary"]["today"],
            "today_quotes": overview["quote_summary"]["today"],
            "today_orders": overview["order_summary"]["today"],
            "today_sales": overview["revenue_summary"]["today_sales"],
            "today_gross_profit": overview["profit_summary"]["today_gross_profit"],
            "today_gross_margin": overview["profit_summary"]["today_gross_margin"],
        }

    @classmethod
    def sales(cls):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT conversion_stage, COUNT(*) AS count FROM sales_conversion_records GROUP BY conversion_stage")
        stages = {row["conversion_stage"]: row["count"] for row in cursor.fetchall()}
        pending = cls._count(cursor, "follow_up_tasks", "task_status = 'pending'")
        cursor.execute("SELECT id, customer_name, destination, conversion_probability, next_best_action FROM sales_conversion_records WHERE conversion_stage IN ('high_intent', 'accepted') OR conversion_probability >= 0.65 ORDER BY conversion_probability DESC LIMIT 20")
        high_intent = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"pending_follow_up": pending, "conversion_stage_counts": stages, "high_intent_customers": high_intent}

    @classmethod
    def profit(cls):
        conn = get_connection()
        service = ProfitService(conn)
        summary = service.get_summary()
        risks = [row for row in service.list_order_profits() if row["profit_level"] in ("low_profit", "loss") or "missing_resource_cost" in row["risk_flags"]]
        conn.close()
        return {"summary": summary, "risk_order_count": len(risks), "risk_orders": risks}

    @classmethod
    def risks(cls):
        conn = get_connection()
        cursor = conn.cursor()
        orders = ProfitService(conn).list_order_profits()
        summary = cls._risk_summary(cursor, orders)
        types = Counter(flag for order in orders for flag in order["risk_flags"])
        conn.close()
        return {"summary": summary, "order_risk_type_counts": dict(types)}

    @classmethod
    def actions(cls):
        conn = get_connection()
        cursor = conn.cursor()
        ceo = CeoAgentService(conn).daily_report()
        actions = cls._recommended_actions(cursor, ceo)
        conn.close()
        return {"count": len(actions), "actions": actions}
