import argparse
from contextlib import contextmanager
import os
import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from apps.backend.db import get_db_path, get_read_only_connection
from scripts.backup_sqlite import copy_sqlite_database, create_backup


BASELINE_REQUIRED_COLUMNS = {
    "travel_products": {
        "id", "title", "destination", "days", "price", "category", "description", "status",
    },
    "inquiries": {
        "id", "customer_name", "phone", "destination", "people_count", "budget",
        "departure_date", "message", "follow_status", "source", "assigned_sales",
        "priority", "last_contact_at", "next_follow_up_at", "created_at",
    },
    "follow_up_tasks": {
        "id", "inquiry_id", "assigned_sales", "task_title", "task_status", "priority",
        "due_at", "completed_at", "created_at",
    },
    "travel_transport_resources": {
        "id", "destination", "resource_name", "supplier_name", "transport_type",
        "departure_city", "arrival_city", "cost_price", "sale_price", "stock_quantity",
        "sold_quantity", "reserved_quantity", "currency", "available_start_date",
        "available_end_date", "available_dates", "status", "created_at",
    },
    "hotel_room_resources": {
        "id", "destination", "resource_name", "supplier_name", "hotel_name", "room_type",
        "breakfast_included", "max_occupancy", "cost_price", "sale_price",
        "stock_quantity", "sold_quantity", "reserved_quantity", "currency",
        "available_start_date", "available_end_date", "available_dates", "status",
        "created_at",
    },
    "attraction_ticket_resources": {
        "id", "destination", "resource_name", "supplier_name", "cost_price", "sale_price",
        "stock_quantity", "sold_quantity", "reserved_quantity", "currency",
        "available_start_date", "available_end_date", "available_dates", "status",
        "created_at",
    },
    "restaurant_meal_resources": {
        "id", "destination", "resource_name", "supplier_name", "meal_type",
        "price_per_person", "cost_price", "sale_price", "stock_quantity",
        "sold_quantity", "reserved_quantity", "currency", "available_start_date",
        "available_end_date", "available_dates", "status", "created_at",
    },
    "activity_resources": {
        "id", "destination", "resource_name", "supplier_name", "activity_type", "duration",
        "suitable_people", "cost_price", "sale_price", "stock_quantity", "sold_quantity",
        "reserved_quantity", "currency", "available_start_date", "available_end_date",
        "available_dates", "status", "created_at",
    },
    "orders": {
        "id", "order_no", "inquiry_id", "customer_name", "phone", "destination",
        "people_count", "total_amount", "paid_amount", "order_status", "payment_status",
        "fulfillment_status", "created_at", "updated_at",
    },
    "order_items": {
        "id", "order_id", "resource_type", "resource_id", "quantity", "unit_price",
        "total_price",
    },
    "order_documents": {
        "id", "order_id", "customer_name", "document_type", "document_number",
        "file_name", "file_url", "ocr_status", "ocr_raw_text", "verified_status",
        "created_at",
    },
    "insurance_products": {
        "id", "name", "provider", "coverage_summary", "price", "status",
    },
    "order_insurances": {
        "id", "order_id", "insurance_product_id", "insured_customer_name", "price",
    },
    "order_contracts": {
        "id", "order_id", "contract_no", "contract_status", "contract_content", "signed_at",
    },
    "order_reminders": {
        "id", "order_id", "reminder_type", "title", "message", "remind_at", "status",
    },
    "payment_events": {
        "id", "payment_event_id", "order_id", "event_status", "response_json",
        "created_at", "processed_at",
    },
    "quotes": {
        "id", "quote_no", "inquiry_id", "customer_name", "phone", "destination",
        "people_count", "customer_budget", "target_margin", "base_cost", "base_price",
        "dynamic_adjustment", "final_price", "estimated_profit", "estimated_margin",
        "quote_status", "pricing_strategy", "risk_flags", "recommendation",
        "departure_date", "converted_order_id", "created_at", "updated_at",
    },
    "quote_items": {
        "id", "quote_id", "resource_type", "resource_id", "resource_name", "quantity",
        "unit_cost", "unit_price", "total_cost", "total_price", "margin", "created_at",
    },
    "sales_conversion_records": {
        "id", "inquiry_id", "quote_id", "customer_name", "phone", "destination", "budget",
        "final_price", "conversion_probability", "conversion_stage",
        "customer_objections_json", "recommended_actions_json", "follow_up_script",
        "risk_flags_json", "next_best_action", "assigned_sales", "created_at", "updated_at",
    },
    "content_campaigns": {
        "id", "campaign_name", "destination", "product_theme", "target_audience",
        "platform", "content_type", "title", "body", "hashtags_json", "call_to_action",
        "related_product_id", "related_resource_ids_json", "estimated_margin",
        "priority_score", "status", "published_at", "created_at", "updated_at",
    },
    "customer_profiles": {
        "id", "customer_name", "phone", "customer_level", "total_orders", "total_spent",
        "total_profit", "preferred_destinations_json", "preferred_budget_range",
        "last_order_at", "next_repurchase_date", "repurchase_probability",
        "lifecycle_stage", "risk_flags_json", "recommendation_text", "created_at",
        "updated_at",
    },
    "repurchase_tasks": {
        "id", "customer_profile_id", "customer_name", "phone", "recommended_destination",
        "recommended_product_id", "reason", "priority", "due_date", "status",
        "assigned_sales", "created_at", "completed_at",
    },
    "supplier_performance": {
        "id", "supplier_name", "resource_type", "destination", "total_resources",
        "total_orders", "total_revenue", "total_cost", "total_profit", "average_margin",
        "stockout_count", "cancellation_count", "performance_score", "risk_flags_json",
        "recommendation_text", "created_at", "updated_at",
    },
    "procurement_suggestions": {
        "id", "supplier_name", "resource_type", "destination", "suggested_action",
        "suggested_quantity", "reason", "priority", "status", "created_at", "updated_at",
    },
    "finance_records": {
        "id", "order_id", "record_type", "amount", "direction", "counterparty",
        "due_date", "paid_at", "status", "risk_flags_json", "note", "created_at",
        "updated_at",
    },
    "reconciliation_reports": {
        "id", "report_date", "total_receivable", "total_received", "total_payable",
        "total_paid", "gross_profit", "risk_amount", "risk_flags_json",
        "recommendation_text", "created_at",
    },
    "operation_audit_logs": {
        "id", "operation_type", "module_name", "resource_type", "resource_id", "actor",
        "request_id", "status", "detail_json", "created_at",
    },
}
CORE_APP_TABLES = set(BASELINE_REQUIRED_COLUMNS)

FORBIDDEN_MIGRATION_PATTERNS = {
    "op.drop_table": "table removal operation",
    "op.drop_column": "column removal operation",
    "drop table": "raw table removal SQL",
    "drop column": "raw column removal SQL",
    "truncate": "table clear operation",
    "delete from": "bulk row removal SQL",
}

WRITE_COMMANDS = {"upgrade", "stamp-existing"}
KNOWN_APP_ENVS = {"development", "staging", "production"}
WRAPPER_TOKEN_ENV = "SZ_TRAVEL_ALEMBIC_WRAPPER_TOKEN"


def build_config(database_url=None):
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    resolved_url = database_url or resolve_database_url()
    config.attributes["database_url"] = resolved_url
    config.set_main_option("sqlalchemy.url", resolved_url)
    return config


def resolve_database_url(database_url=None):
    if database_url:
        return database_url
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        return configured_url
    return f"sqlite:///{get_db_path().as_posix()}"


def render_safe_database_url(database_url):
    parsed = make_url(database_url)
    if parsed.drivername.startswith("sqlite"):
        return str(sqlite_path_from_url(database_url) or parsed)
    return parsed.render_as_string(hide_password=True)


def sqlite_path_from_url(database_url):
    parsed = make_url(database_url)
    if not parsed.drivername.startswith("sqlite"):
        return None
    if parsed.database in (None, "", ":memory:"):
        return None
    path = Path(parsed.database)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def latest_head(config):
    return ScriptDirectory.from_config(config).get_current_head()


@contextmanager
def authorize_alembic_write(config, command_name):
    token = secrets.token_urlsafe(32)
    previous_token = os.environ.get(WRAPPER_TOKEN_ENV)
    config.attributes["migration_command"] = (
        "stamp" if command_name == "stamp-existing" else command_name
    )
    config.attributes["wrapper_authorization_token"] = token
    os.environ[WRAPPER_TOKEN_ENV] = token
    try:
        yield
    finally:
        config.attributes.pop("migration_command", None)
        config.attributes.pop("wrapper_authorization_token", None)
        if previous_token is None:
            os.environ.pop(WRAPPER_TOKEN_ENV, None)
        else:
            os.environ[WRAPPER_TOKEN_ENV] = previous_token


def scan_for_destructive_migrations():
    versions_dir = PROJECT_ROOT / "alembic" / "versions"
    violations = []
    for path in sorted(versions_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        for pattern, reason in FORBIDDEN_MIGRATION_PATTERNS.items():
            if pattern in text:
                violations.append((path, pattern, reason))
    if violations:
        details = "\n".join(
            f"- {path.relative_to(PROJECT_ROOT)} contains {pattern!r}: {reason}"
            for path, pattern, reason in violations
        )
        raise RuntimeError(
            "Potentially destructive migration detected. Stop and request "
            f"manual approval before continuing:\n{details}"
        )
    return []


def sqlite_state(db_path):
    if db_path is None:
        return {
            "sqlite": False,
            "exists": False,
            "tables": [],
            "app_table_count": 0,
            "has_app_tables": False,
            "has_alembic_version": False,
            "current_revision": None,
            "quick_check": None,
        }
    if not db_path.exists():
        return {
            "sqlite": True,
            "db_path": str(db_path),
            "exists": False,
            "tables": [],
            "app_table_count": 0,
            "has_app_tables": False,
            "has_alembic_version": False,
            "current_revision": None,
            "quick_check": None,
        }

    conn = get_read_only_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA quick_check")
        quick_check = cursor.fetchone()[0]
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = sorted(row[0] for row in cursor.fetchall())
        has_alembic_version = "alembic_version" in tables
        current_revision = None
        if has_alembic_version:
            cursor.execute("SELECT version_num FROM alembic_version")
            row = cursor.fetchone()
            current_revision = row[0] if row else None
    finally:
        conn.close()

    app_tables = sorted(set(tables).intersection(CORE_APP_TABLES))
    return {
        "sqlite": True,
        "db_path": str(db_path),
        "exists": True,
        "tables": tables,
        "app_table_count": len(app_tables),
        "has_app_tables": bool(app_tables),
        "has_alembic_version": has_alembic_version,
        "current_revision": current_revision,
        "quick_check": quick_check,
    }


def baseline_schema_report(db_path):
    if db_path is None or not db_path.exists():
        return {
            "schema_ok": False,
            "quick_check": None,
            "missing_tables": sorted(BASELINE_REQUIRED_COLUMNS),
            "missing_columns": {},
        }

    conn = get_read_only_connection(db_path)
    try:
        quick_check_rows = [row[0] for row in conn.execute("PRAGMA quick_check")]
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing_tables = sorted(set(BASELINE_REQUIRED_COLUMNS) - tables)
        missing_columns = {}
        for table, required_columns in BASELINE_REQUIRED_COLUMNS.items():
            if table not in tables:
                continue
            existing_columns = {
                row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')
            }
            missing = sorted(required_columns - existing_columns)
            if missing:
                missing_columns[table] = missing
    finally:
        conn.close()

    quick_check = "ok" if quick_check_rows == ["ok"] else "; ".join(quick_check_rows)
    return {
        "schema_ok": (
            quick_check == "ok"
            and not missing_tables
            and not missing_columns
        ),
        "quick_check": quick_check,
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
    }


def format_schema_validation_error(report):
    details = [f"quick_check={report['quick_check']}"]
    if report["missing_tables"]:
        details.append(
            "missing_tables=" + ",".join(report["missing_tables"])
        )
    if report["missing_columns"]:
        formatted_columns = ";".join(
            f"{table}:{','.join(columns)}"
            for table, columns in sorted(report["missing_columns"].items())
        )
        details.append("missing_columns=" + formatted_columns)
    return " | ".join(details)


def ensure_write_is_allowed(args, config, database_url):
    app_env = (os.getenv("APP_ENV") or "development").strip().lower()
    if args.command in WRITE_COMMANDS and app_env not in KNOWN_APP_ENVS:
        raise RuntimeError(
            "Invalid APP_ENV for database write operation. "
            "Use development, staging, or production."
        )
    if args.command in WRITE_COMMANDS and app_env == "production":
        if not args.confirm_production:
            raise RuntimeError(
                "APP_ENV=production requires --confirm-production for database "
                "write operations. Verify backups, target path, and approval first."
            )

    scan_for_destructive_migrations()

    db_path = sqlite_path_from_url(database_url)
    if args.command in WRITE_COMMANDS and db_path is None:
        raise RuntimeError(
            "Write migrations currently require a file-based SQLite target. "
            "PostgreSQL support is reserved for a separately reviewed phase."
        )
    state = sqlite_state(db_path)
    if args.command == "upgrade" and state["exists"]:
        if state["has_app_tables"] and not state["has_alembic_version"]:
            raise RuntimeError(
                "Existing SQLite database has application tables but no "
                "alembic_version table. Run 'stamp-existing' after manual "
                "schema review instead of running upgrade."
            )
    if args.command == "stamp-existing":
        if db_path is None:
            raise RuntimeError("stamp-existing currently requires a file-based SQLite target.")
        if not state["exists"] or not state["has_app_tables"]:
            raise RuntimeError(
                "stamp-existing requires an existing application database. "
                "Use upgrade for a new empty database."
            )
        schema_report = baseline_schema_report(db_path)
        if not schema_report["schema_ok"]:
            raise RuntimeError(
                "Existing SQLite schema does not match the required baseline. "
                "Fix or migrate the schema before stamp-existing: "
                f"{format_schema_validation_error(schema_report)}"
            )

    return {
        "app_env": app_env,
        "sqlite_path": db_path,
        "state": state,
        "head": latest_head(config),
    }


def backup_before_write(sqlite_path, backup_dir=None):
    if sqlite_path is None or not sqlite_path.exists():
        return None
    return create_backup(source_path=sqlite_path, backup_dir=backup_dir)


def restore_from_backup(backup_path, sqlite_path):
    if backup_path is None or sqlite_path is None:
        return None
    return copy_sqlite_database(backup_path, sqlite_path)


def print_check_result(config, database_url):
    scan_for_destructive_migrations()
    db_path = sqlite_path_from_url(database_url)
    state = sqlite_state(db_path)
    schema_report = baseline_schema_report(db_path)
    print(f"target={render_safe_database_url(database_url)}")
    print(f"head={latest_head(config)}")
    print(f"sqlite={state['sqlite']}")
    print(f"exists={state['exists']}")
    print(f"has_app_tables={state['has_app_tables']}")
    print(f"app_table_count={state['app_table_count']}")
    print(f"has_alembic_version={state['has_alembic_version']}")
    print(f"current_revision={state['current_revision']}")
    print(f"quick_check={state['quick_check']}")
    print(f"baseline_schema_ok={schema_report['schema_ok']}")
    print(f"missing_tables={','.join(schema_report['missing_tables'])}")
    print(
        "missing_columns="
        + ";".join(
            f"{table}:{','.join(columns)}"
            for table, columns in sorted(schema_report["missing_columns"].items())
        )
    )
    print("destructive_migration_scan=ok")


def run(args):
    database_url = resolve_database_url(args.database_url)
    config = build_config(database_url)

    if args.command == "check":
        print_check_result(config, database_url)
        return
    if args.command == "history":
        command.history(config, verbose=args.verbose)
        return
    if args.command == "heads":
        command.heads(config, verbose=args.verbose)
        return
    if args.command == "current":
        command.current(config, verbose=args.verbose)
        return

    preflight = ensure_write_is_allowed(args, config, database_url)
    backup_path = backup_before_write(preflight["sqlite_path"], args.backup_dir)
    if backup_path is not None:
        print(f"pre_migration_backup={backup_path}")
    else:
        print("pre_migration_backup=not_required_for_new_database")

    try:
        with authorize_alembic_write(config, args.command):
            if args.command == "upgrade":
                command.upgrade(config, args.revision)
            elif args.command == "stamp-existing":
                command.stamp(config, args.revision)
            else:
                raise RuntimeError(f"Unsupported command: {args.command}")
    except Exception:
        restored = restore_from_backup(backup_path, preflight["sqlite_path"])
        if restored is not None:
            print(f"migration_failed_restored_from_backup={backup_path}")
        raise

    command.current(config, verbose=False)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Safe Alembic migration wrapper for the Shenzhen Travel AI backend. "
            "Production write operations require --confirm-production."
        )
    )
    parser.add_argument(
        "command",
        choices=("check", "history", "heads", "current", "upgrade", "stamp-existing"),
        help=(
            "check/history/heads/current are read-only. upgrade applies migrations. "
            "stamp-existing marks a reviewed existing SQLite schema as current."
        ),
    )
    parser.add_argument("--revision", default="head", help="Target revision. Defaults to head.")
    parser.add_argument("--database-url", help="Override DATABASE_URL for this run.")
    parser.add_argument("--backup-dir", help="Directory for pre-migration SQLite backups.")
    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="Required for write operations when APP_ENV=production.",
    )
    parser.add_argument("--verbose", action="store_true", help="Show verbose Alembic output.")
    return parser.parse_args()


def main():
    run(parse_args())


if __name__ == "__main__":
    main()
