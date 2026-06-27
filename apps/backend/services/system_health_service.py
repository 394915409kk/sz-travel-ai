from importlib.util import find_spec
from pathlib import Path

from apps.backend.db import get_db_path, get_read_only_connection
from apps.backend.security import security_config_status
from apps.backend.services.inventory_service import RESOURCE_TABLES
from apps.backend.services.profit_service import ProfitService
from scripts.backup_sqlite import resolve_backup_dir


REQUIRED_TABLES = (
    "travel_products", "inquiries", "follow_up_tasks",
    "travel_transport_resources", "hotel_room_resources",
    "attraction_ticket_resources", "restaurant_meal_resources",
    "activity_resources", "orders", "order_items", "order_documents",
    "insurance_products", "order_insurances", "order_contracts",
    "order_reminders", "payment_events",
    "quotes", "quote_items", "sales_conversion_records",
    "content_campaigns", "customer_profiles", "repurchase_tasks",
    "supplier_performance", "procurement_suggestions", "finance_records",
    "reconciliation_reports", "operation_audit_logs",
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
    "audit": ("apps.backend.api.audit", "/audit-logs"),
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
        db_path = get_db_path()
        if not db_path.exists():
            return {
                "accessible": False,
                "database_missing": True,
                "quick_check": None,
                "db_path": str(db_path),
                "readable": False,
                "writable": False,
                "required_table_count": len(REQUIRED_TABLES),
                "existing_required_table_count": 0,
                "missing_tables": list(REQUIRED_TABLES),
                "healthy": False,
                "reason_codes": ["database_missing"],
            }

        try:
            conn = get_read_only_connection(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA quick_check")
            quick_check = cursor.fetchone()[0]
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            existing = {row["name"] for row in cursor.fetchall()}
            missing = [table for table in REQUIRED_TABLES if table not in existing]
            conn.close()
            reason_codes = []
            if quick_check != "ok":
                reason_codes.append("database_integrity_failed")
            if missing:
                reason_codes.append("required_tables_missing")
            return {
                "accessible": True,
                "database_missing": False,
                "quick_check": quick_check,
                "db_path": str(db_path),
                "readable": True,
                "writable": db_path.exists() and db_path.stat().st_size >= 0,
                "required_table_count": len(REQUIRED_TABLES),
                "existing_required_table_count": len(REQUIRED_TABLES) - len(missing),
                "missing_tables": missing,
                "healthy": quick_check == "ok" and not missing,
                "reason_codes": reason_codes,
            }
        except Exception as exc:
            return {
                "accessible": False,
                "database_missing": False,
                "quick_check": None,
                "db_path": str(db_path),
                "missing_tables": list(REQUIRED_TABLES),
                "healthy": False,
                "reason_codes": ["database_unreadable"],
                "error": str(exc),
            }

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
        conn = get_read_only_connection()
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
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM payment_events
                WHERE order_id = ? AND event_status = 'processed'
                """,
                (row["id"],),
            )
            if cursor.fetchone()["count"] == 0:
                risks.append(cls._risk("critical", "PAYMENT_LEDGER_RISK", f"已支付订单 {row['order_no']} 缺少已处理支付事件", {"order_id": row["id"]}))
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

    @staticmethod
    def security():
        return security_config_status()

    @staticmethod
    def backup():
        backup_dir = resolve_backup_dir()
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            writable_probe = backup_dir / ".write_check"
            writable_probe.write_text("ok", encoding="utf-8")
            writable_probe.unlink(missing_ok=True)
            return {
                "backup_directory": str(backup_dir),
                "exists": True,
                "writable": True,
                "backup_directory_ok": True,
                "healthy": True,
            }
        except Exception as exc:
            return {
                "backup_directory": str(backup_dir),
                "exists": backup_dir.exists(),
                "writable": False,
                "backup_directory_ok": False,
                "healthy": False,
                "error": str(exc),
            }

    @staticmethod
    def migration():
        db_path = get_db_path()
        database_missing = not db_path.exists()
        current_revision = None
        has_version_table = False
        table_count = 0
        quick_check = None
        error = None

        if not database_missing:
            try:
                conn = get_read_only_connection(db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA quick_check")
                    quick_check = cursor.fetchone()[0]
                    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
                    tables = {row["name"] for row in cursor.fetchall()}
                    table_count = len(tables)
                    has_version_table = "alembic_version" in tables
                    if has_version_table:
                        cursor.execute("SELECT version_num FROM alembic_version")
                        row = cursor.fetchone()
                        current_revision = row["version_num"] if row else None
                finally:
                    conn.close()
            except Exception as exc:
                error = str(exc)

        head_revision = None
        head_error = None
        try:
            from scripts.migrate_db import build_config, latest_head

            head_revision = latest_head(build_config())
        except Exception as exc:
            head_error = str(exc)

        current_is_head = bool(
            current_revision and head_revision and current_revision == head_revision
        )
        healthy = error is None and head_error is None and current_is_head
        reason_codes = []
        if database_missing:
            reason_codes.append("database_missing")
        if not database_missing and not has_version_table:
            reason_codes.append("alembic_version_missing")
        if not current_is_head:
            reason_codes.append("migration_not_ready")
        if error is not None:
            reason_codes.append("database_unreadable")
        if head_error is not None:
            reason_codes.append("migration_head_unavailable")

        return {
            "db_path": str(db_path),
            "database_missing": database_missing,
            "table_count": table_count,
            "quick_check": quick_check,
            "has_alembic_version": has_version_table,
            "current_revision": current_revision,
            "head_revision": head_revision,
            "current_is_head": current_is_head,
            "required_for_production": True,
            "healthy": healthy,
            "reason_codes": reason_codes,
            "error": error,
            "head_error": head_error,
        }

    @classmethod
    def readiness(cls, route_paths):
        database = cls.database()
        modules = cls.modules(route_paths)
        risks = (
            cls.risks()
            if database.get("healthy")
            else {
                "count": 1,
                "critical_count": 1,
                "warning_count": 0,
                "risks": [
                    cls._risk(
                        "critical",
                        "DATABASE_NOT_READY",
                        "数据库缺失、不可读或关键表不完整。",
                        {"reason_codes": database.get("reason_codes", [])},
                    )
                ],
            }
        )
        security = cls.security()
        backup = cls.backup()
        migration = cls.migration()
        app_env = security["app_env"]
        database_ok = database.get("healthy", False)
        required_tables_ok = not database.get("missing_tables")
        module_registration_ok = modules["healthy"]
        backup_directory_ok = backup["backup_directory_ok"]
        security_config_ok = security["security_config_ok"]
        migration_version_ok = migration["current_is_head"]
        production_migration_ok = app_env != "production" or migration_version_ok
        database_missing = database.get("database_missing", False)
        alembic_version_missing = (
            app_env == "production"
            and not database_missing
            and not migration["has_alembic_version"]
        )
        migration_not_ready = (
            app_env == "production" and not migration_version_ok
        )
        ready = (
            database_ok
            and required_tables_ok
            and module_registration_ok
            and backup_directory_ok
            and security_config_ok
            and production_migration_ok
            and risks["critical_count"] == 0
        )
        recommendations = []
        if not database_ok or not required_tables_ok:
            recommendations.append("先修复数据库可访问性和关键表结构。")
        if not module_registration_ok:
            recommendations.append("检查 FastAPI 路由注册和模块导入。")
        if not backup_directory_ok:
            recommendations.append("修复 SQLite 备份目录权限。")
        if not security_config_ok:
            recommendations.extend(security["recommendations"])
        if app_env == "production" and not migration_version_ok:
            recommendations.append("生产环境必须先完成 Alembic 迁移或 stamp-existing。")
        if risks["critical_count"] > 0:
            recommendations.append("先修复关键一致性风险，再进入内测。")
        if not recommendations:
            recommendations.append("系统通过内测就绪检查；警告项仍需运营人员持续复核。")
        return {
            "app_env": app_env,
            "database_ok": database_ok,
            "required_tables_ok": required_tables_ok,
            "module_registration_ok": module_registration_ok,
            "backup_directory_ok": backup_directory_ok,
            "security_config_ok": security_config_ok,
            "migration_version_ok": migration_version_ok,
            "database_missing": database_missing,
            "alembic_version_missing": alembic_version_missing,
            "migration_not_ready": migration_not_ready,
            "reason_codes": sorted(
                set(database.get("reason_codes", []))
                | (
                    set(migration.get("reason_codes", []))
                    if app_env == "production"
                    else set()
                )
            ),
            "migration_current_revision": migration["current_revision"],
            "migration_head_revision": migration["head_revision"],
            "critical_risks_count": risks["critical_count"],
            "warnings_count": risks["warning_count"],
            "ready": ready,
            "status": "ready" if ready else "not_ready",
            "checks": {
                "database": database_ok,
                "required_tables": required_tables_ok,
                "modules": module_registration_ok,
                "backup_directory": backup_directory_ok,
                "security_config": security_config_ok,
                "migration_current": production_migration_ok,
                "no_critical_risks": risks["critical_count"] == 0,
            },
            "warning_count": risks["warning_count"],
            "recommendations": recommendations,
            "recommendation": recommendations[0],
        }

    @classmethod
    def full_health(cls, route_paths):
        database = cls.database()
        modules = cls.modules(route_paths)
        risks = (
            cls.risks()
            if database.get("healthy")
            else {
                "count": 1,
                "critical_count": 1,
                "warning_count": 0,
                "risks": [
                    cls._risk(
                        "critical",
                        "DATABASE_NOT_READY",
                        "数据库缺失、不可读或关键表不完整。",
                        {"reason_codes": database.get("reason_codes", [])},
                    )
                ],
            }
        )
        readiness = cls.readiness(route_paths)
        return {
            "status": "ok" if readiness["ready"] else "degraded",
            "database": database,
            "modules": modules,
            "security": cls.security(),
            "backup": cls.backup(),
            "migration": cls.migration(),
            "risks": risks,
            "readiness": readiness,
        }
