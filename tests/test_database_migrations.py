import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from apps.backend.init_db import init_database, should_auto_init_database


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_ENV = {
    key: value
    for key, value in os.environ.items()
    if key not in {"DATABASE_URL", "SQLITE_DB_PATH", "SQLITE_BACKUP_DIR", "APP_ENV"}
}


def run_migration_command(*args, sqlite_path, backup_dir):
    env = {
        **BASE_ENV,
        "SQLITE_DB_PATH": str(sqlite_path),
        "SQLITE_BACKUP_DIR": str(backup_dir),
        "APP_ENV": "development",
    }
    return subprocess.run(
        [sys.executable, "scripts/migrate_db.py", *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def sqlite_tables(db_path):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        return {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()


def sqlite_revision(db_path):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT version_num FROM alembic_version")
        return cursor.fetchone()[0]
    finally:
        conn.close()


def test_new_sqlite_database_can_upgrade_to_head(tmp_path):
    db_path = tmp_path / "new-migration.db"
    backup_dir = tmp_path / "backups"

    result = run_migration_command("upgrade", sqlite_path=db_path, backup_dir=backup_dir)

    assert result.returncode == 0, result.stderr
    tables = sqlite_tables(db_path)
    assert "alembic_version" in tables
    assert "travel_products" in tables
    assert "orders" in tables
    assert sqlite_revision(db_path) == "20260626_0001"
    assert "pre_migration_backup=not_required_for_new_database" in result.stdout


def test_existing_unversioned_sqlite_requires_stamp_existing(tmp_path, monkeypatch):
    db_path = tmp_path / "existing-unversioned.db"
    backup_dir = tmp_path / "backups"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
    monkeypatch.setenv("SQLITE_BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("APP_ENV", "development")

    init_database()

    upgrade = run_migration_command("upgrade", sqlite_path=db_path, backup_dir=backup_dir)
    assert upgrade.returncode != 0
    assert "stamp-existing" in upgrade.stderr

    stamped = run_migration_command(
        "stamp-existing",
        sqlite_path=db_path,
        backup_dir=backup_dir,
    )
    assert stamped.returncode == 0, stamped.stderr
    assert sqlite_revision(db_path) == "20260626_0001"
    assert list(backup_dir.glob("existing-unversioned-*.sqlite3"))


def test_production_startup_auto_init_is_disabled(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("AUTO_INIT_DB_ON_STARTUP", raising=False)

    assert should_auto_init_database() is False

    monkeypatch.setenv("APP_ENV", "development")
    assert should_auto_init_database() is True

    monkeypatch.setenv("AUTO_INIT_DB_ON_STARTUP", "false")
    assert should_auto_init_database() is False
