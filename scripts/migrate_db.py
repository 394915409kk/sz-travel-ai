import argparse
import os
import shutil
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from apps.backend.db import get_db_path
from scripts.backup_sqlite import create_backup


CORE_APP_TABLES = {
    "travel_products",
    "inquiries",
    "follow_up_tasks",
    "travel_transport_resources",
    "hotel_room_resources",
    "attraction_ticket_resources",
    "restaurant_meal_resources",
    "activity_resources",
    "orders",
    "order_items",
    "payment_events",
    "quotes",
    "quote_items",
    "sales_conversion_records",
    "content_campaigns",
    "customer_profiles",
    "repurchase_tasks",
    "supplier_performance",
    "procurement_suggestions",
    "finance_records",
    "reconciliation_reports",
    "operation_audit_logs",
}

FORBIDDEN_MIGRATION_PATTERNS = {
    "op.drop_table": "table removal operation",
    "op.drop_column": "column removal operation",
    "drop table": "raw table removal SQL",
    "drop column": "raw column removal SQL",
    "truncate": "table clear operation",
    "delete from": "bulk row removal SQL",
}

WRITE_COMMANDS = {"upgrade", "stamp-existing"}


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

    conn = sqlite3.connect(db_path)
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


def ensure_write_is_allowed(args, config, database_url):
    app_env = (os.getenv("APP_ENV") or "development").strip().lower()
    if args.command in WRITE_COMMANDS and app_env == "production":
        if not args.confirm_production:
            raise RuntimeError(
                "APP_ENV=production requires --confirm-production for database "
                "write operations. Verify backups, target path, and approval first."
            )

    scan_for_destructive_migrations()

    db_path = sqlite_path_from_url(database_url)
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
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, sqlite_path)
    return sqlite_path


def print_check_result(config, database_url):
    scan_for_destructive_migrations()
    db_path = sqlite_path_from_url(database_url)
    state = sqlite_state(db_path)
    print(f"target={render_safe_database_url(database_url)}")
    print(f"head={latest_head(config)}")
    print(f"sqlite={state['sqlite']}")
    print(f"exists={state['exists']}")
    print(f"has_app_tables={state['has_app_tables']}")
    print(f"app_table_count={state['app_table_count']}")
    print(f"has_alembic_version={state['has_alembic_version']}")
    print(f"current_revision={state['current_revision']}")
    print(f"quick_check={state['quick_check']}")
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
