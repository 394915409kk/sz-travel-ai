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
    if key not in {
        "DATABASE_URL",
        "SQLITE_DB_PATH",
        "SQLITE_BACKUP_DIR",
        "APP_ENV",
        "SZ_TRAVEL_ALEMBIC_WRAPPER_TOKEN",
    }
}


def run_migration_command(
    *args,
    sqlite_path,
    backup_dir,
    app_env="development",
):
    env = {
        **BASE_ENV,
        "SQLITE_DB_PATH": str(sqlite_path),
        "SQLITE_BACKUP_DIR": str(backup_dir),
        "APP_ENV": app_env,
    }
    return subprocess.run(
        [sys.executable, "scripts/migrate_db.py", *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def run_direct_alembic(
    *args,
    sqlite_path,
    backup_dir,
    app_env="production",
    extra_env=None,
):
    env = {
        **BASE_ENV,
        "SQLITE_DB_PATH": str(sqlite_path),
        "SQLITE_BACKUP_DIR": str(backup_dir),
        "APP_ENV": app_env,
        **(extra_env or {}),
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
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


def test_production_direct_alembic_write_is_blocked(tmp_path):
    for command_name in ("upgrade", "stamp"):
        db_path = tmp_path / f"direct-production-{command_name}.db"
        backup_dir = tmp_path / f"backups-{command_name}"

        direct = run_direct_alembic(
            command_name,
            "head",
            sqlite_path=db_path,
            backup_dir=backup_dir,
            extra_env={"SZ_TRAVEL_ALEMBIC_WRAPPER_TOKEN": "forged-token"},
        )

        assert direct.returncode != 0
        assert "Direct Alembic write operations are disabled in production" in direct.stderr
        assert not db_path.exists()
        assert not backup_dir.exists()


def test_production_wrapper_requires_confirmation_and_authorizes_write(tmp_path):
    db_path = tmp_path / "wrapper-production.db"
    backup_dir = tmp_path / "backups"

    blocked = run_migration_command(
        "upgrade",
        sqlite_path=db_path,
        backup_dir=backup_dir,
        app_env="production",
    )
    assert blocked.returncode != 0
    assert "--confirm-production" in blocked.stderr
    assert not db_path.exists()

    confirmed = run_migration_command(
        "upgrade",
        "--confirm-production",
        sqlite_path=db_path,
        backup_dir=backup_dir,
        app_env="production",
    )
    assert confirmed.returncode == 0, confirmed.stderr
    assert sqlite_revision(db_path) == "20260626_0001"


def test_non_sqlite_write_target_is_reserved_for_future_review(tmp_path):
    result = run_migration_command(
        "upgrade",
        "--confirm-production",
        "--database-url",
        "postgresql://placeholder:placeholder@127.0.0.1:1/placeholder",
        sqlite_path=tmp_path / "unused.db",
        backup_dir=tmp_path / "backups",
        app_env="production",
    )

    assert result.returncode != 0
    assert "PostgreSQL support is reserved" in result.stderr
    assert not (tmp_path / "unused.db").exists()


def test_unknown_app_env_fails_closed_for_migrations_and_startup(
    tmp_path,
    monkeypatch,
):
    result = run_migration_command(
        "upgrade",
        sqlite_path=tmp_path / "invalid-env.db",
        backup_dir=tmp_path / "backups",
        app_env="prod",
    )

    assert result.returncode != 0
    assert "Invalid APP_ENV" in result.stderr
    assert not (tmp_path / "invalid-env.db").exists()

    direct_result = run_direct_alembic(
        "upgrade",
        "head",
        sqlite_path=tmp_path / "invalid-env-direct.db",
        backup_dir=tmp_path / "direct-backups",
        app_env="prod",
    )
    assert direct_result.returncode != 0
    assert "Invalid APP_ENV" in direct_result.stderr
    assert not (tmp_path / "invalid-env-direct.db").exists()

    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTO_INIT_DB_ON_STARTUP", "true")
    assert should_auto_init_database() is False


def test_incomplete_sqlite_schema_cannot_be_stamped(tmp_path):
    db_path = tmp_path / "incomplete.db"
    backup_dir = tmp_path / "backups"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE travel_products (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    stamped = run_migration_command(
        "stamp-existing",
        sqlite_path=db_path,
        backup_dir=backup_dir,
    )

    assert stamped.returncode != 0
    assert "does not match the required baseline" in stamped.stderr
    assert "missing_tables=" in stamped.stderr
    assert "missing_columns=travel_products:" in stamped.stderr
    assert "alembic_version" not in sqlite_tables(db_path)
    assert not backup_dir.exists()


def test_container_startup_does_not_run_database_migrations():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "migrate_db.py upgrade" not in dockerfile
    assert "migrate_db.py upgrade" not in compose
    assert "CMD uvicorn " in dockerfile
    assert "uvicorn apps.backend.main:app" in compose


def test_production_startup_auto_init_is_disabled(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("AUTO_INIT_DB_ON_STARTUP", raising=False)

    assert should_auto_init_database() is False

    monkeypatch.setenv("APP_ENV", "development")
    assert should_auto_init_database() is True

    monkeypatch.setenv("AUTO_INIT_DB_ON_STARTUP", "false")
    assert should_auto_init_database() is False
