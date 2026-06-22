from importlib.util import find_spec
from pathlib import Path

from apps.backend.db import get_connection
from apps.backend.services.inventory_service import RESOURCE_TABLES
from apps.backend.services.profit_service import ProfitService


REQUIRED_TABLES = (
    "travel_products", "inquiries", "follow_up_tasks",
    "travel_transport_resources", "hotel_room_resources",
    "attraction_ticket_resources", "restaurant_meal_resources",
    "activity_resources", "orders", "order_items", "payment_events",
    "quotes", "quote_items", "sales_conversion_records",
    "content_campaigns", "customer_profiles", "repurchase_tasks",
    "supplier_performance", "procurement_suggestions", "finance_records",
    "reconciliation_reports",
)

MODULES = {
    "crm": ("apps.backend.api.inquiry", "/inquiries"),
    "recommendation": ("apps.backend.api.recommendation", "/recommendations"),
    "follow_up": ("apps.backend.api.follow_up_task", "/follow-up-tasks"),
    "resources": ("apps.backend.api.resource", "/resources"),
    "orders": ("apps.backend.api.order", "/orders"),
    "profit": ("apps.backend.api.profit", "/profit"),
    "ceo_agent": ("apps.backend.api.ceo_agent", "/ceo-agent"),
    "quotes": ("apps.backend.api.quote", "/quotes"),
    "sales_conversion": ("apps.backend.api.sales_conversion", "/sales-conversion"),
    "content_marketing": ("apps.backend.api.content_marketing", "/content-marketing"),
    "customer_lifecycle": ("apps.backend.api.customer_lifecycle", "/customer-lifecycle"),
    "supply_chain": ("apps.backend.api.supply_chain", "/supply-chain"),
    "finance_control": ("apps.backend.api.finance_control", "/finance-control"),
    "dashboard": ("apps.backend.api.dashboard", "/dashboard"),
    "system_health": ("apps.backend.api.system_health", "/system-health"),
}

CORE_TEST_FILES = (
    "test_business_flow.py", "test_order_consistency.py",
    "test_order_fulfillment.py", "test_profit_ceo_agent.py",
    "test_quote_dynamic_pricing.py", "test_sales_conversion.py",
    "test_content_marketing.py", "test_customer_lifecycle.py",
    "test_supply_chain.py", "test_finance_control.py",
    "test_dashboard.py", "test_system_health.py",
)


class SystemHealthService:
    """执行只读结构与一致性检查；不会自动修复或改变核心业务状态。"""

    @classmethod
    def database(cls):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA quick_check")
            quick_check = cursor.fetchone()[0]
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            existing = {row["name"] for row in cursor.fetchall()}
            missing = [table for table in REQUIRED_TABLES if table not in existing]
            conn.close()
            return {
                "accessible": True, "quick_check": quick_check,
                "required_table_count": len(REQUIRED_TABLES),
                "existing_required_table_count": len(REQUIRED_TABLES) - len(missing),
                "missing_tables": missing,
                "healthy": quick_check == "ok" and not missing,
            }
        except Exception as exc:
            return {"accessible": False, "quick_check": None, "missing_tables": list(REQUIRED_TABLES), "healthy": False, "error": str(exc)}

    @staticmethod
    def modules(route_paths):
        results = []
        for name, (module_name, prefix) in MODULES.items():
            importable = find_spec(module_name) is not None
            registered = any(path == prefix or path.startswith(prefix + "/") for path in route_paths)
            results.append({"module": name, "importable": importable, "registered": registered, "healthy": importable and registered})
        return {"healthy": all(item["healthy"] for item in results), "modules": results}

    @classmethod
    def risks(cls):
        conn = get_connection()
        cursor = conn.cursor()
        risks = []
        for resource_type, table in RESOURCE_TABLES.items():
            cursor.execute(f"SELECT id, resource_name, stock_quantity, sold_quantity, reserved_quantity, status FROM {table}")
            for row in cursor.fetchall():
                available = row["stock_quantity"] - row["sold_quantity"] - row["reserved_quantity"]
                if available < 0:
                    risks.append(cls._risk("critical", "NEGATIVE_INVENTORY", f"{resource_type} 资源 {row['id']} 出现负库存", {"resource_type": resource_type, "resource_id": row["id"]}))
                elif available <= 0 and row["status"] == "active":
                    risks.append(cls._risk("warning", "STOCK_SHORTAGE_RISK", f"{resource_type} 资源 {row['id']} 库存不足但仍为 active", {"resource_type": resource_type, "resource_id": row["id"]}))

        cursor.execute("""
            SELECT q.id, q.quote_no FROM quotes AS q
            LEFT JOIN orders AS o ON o.id = q.converted_order_id
            WHERE q.quote_status = 'converted_to_order'
              AND (q.converted_order_id IS NULL OR o.id IS NULL)
        """)
        for row in cursor.fetchall():
            risks.append(cls._risk("critical", "ORDER_STATE_RISK", f"已转换报价 {row['quote_no']} 没有关联有效订单", {"quote_id": row["id"]}))

        profit_service = ProfitService(conn)
        cursor.execute("SELECT id, order_no FROM orders WHERE payment_status = 'mock_paid'")
        for row in cursor.fetchall():
            profit = profit_service.get_order_profit(row["id"])
            if profit is None:
                risks.append(cls._risk("critical", "NEGATIVE_PROFIT_RISK", f"已支付订单 {row['order_no']} 无法计算利润", {"order_id": row["id"]}))

        cursor.execute("""
            SELECT id, order_id, amount FROM finance_records
            WHERE status = 'overdue'
               OR (status = 'pending' AND due_date IS NOT NULL AND date(due_date) < date('now', 'localtime'))
        """)
        for row in cursor.fetchall():
            risks.append(cls._risk("warning", "FINANCE_RECONCILIATION_RISK", f"财务记录 {row['id']} 已逾期", {"record_id": row["id"], "order_id": row["order_id"], "amount": row["amount"]}))
        conn.close()

        tests_dir = Path(__file__).resolve().parents[3] / "tests"
        missing_tests = [name for name in CORE_TEST_FILES if not (tests_dir / name).exists()]
        if missing_tests:
            risks.append(cls._risk("warning", "SYSTEM_HEALTH_RISK", "核心模块测试文件不完整", {"missing_test_files": missing_tests}))
        critical_count = sum(risk["severity"] == "critical" for risk in risks)
        return {"count": len(risks), "critical_count": critical_count, "warning_count": len(risks) - critical_count, "risks": risks}

    @staticmethod
    def _risk(severity, risk_type, message, context):
        return {"severity": severity, "risk_type": risk_type, "message": message, "context": context, "risk_flag": "SYSTEM_HEALTH_RISK"}

    @classmethod
    def readiness(cls, route_paths):
        database = cls.database()
        modules = cls.modules(route_paths)
        risks = cls.risks() if database.get("accessible") else {"count": 0, "critical_count": 1, "warning_count": 0, "risks": []}
        ready = database.get("healthy", False) and modules["healthy"] and risks["critical_count"] == 0
        return {
            "ready": ready,
            "status": "ready" if ready else "not_ready",
            "checks": {
                "database": database.get("healthy", False),
                "modules": modules["healthy"],
                "no_critical_risks": risks["critical_count"] == 0,
            },
            "warning_count": risks["warning_count"],
            "recommendation": (
                "系统通过 MVP 就绪检查；警告项仍需运营人员持续复核。"
                if ready else "先修复数据库、模块注册或关键一致性风险，再进入长期自动化运行。"
            ),
        }

    @classmethod
    def full_health(cls, route_paths):
        database = cls.database()
        modules = cls.modules(route_paths)
        risks = cls.risks() if database.get("accessible") else {"count": 0, "critical_count": 1, "warning_count": 0, "risks": []}
        readiness = cls.readiness(route_paths)
        return {"status": "ok" if readiness["ready"] else "degraded", "database": database, "modules": modules, "risks": risks, "readiness": readiness}
