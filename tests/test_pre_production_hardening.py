import sqlite3

import pytest
from fastapi.testclient import TestClient

from apps.backend.init_db import init_database
from apps.backend.main import app
from apps.backend.services.privacy_service import PrivacyService
from scripts.backup_sqlite import create_backup
from scripts.restore_sqlite import restore_backup


def inquiry_payload():
    return {
        "customer_name": "张三",
        "phone": "13800000000",
        "destination": "塞班",
        "people_count": 2,
        "budget": 12000,
        "message": "内测鉴权客户咨询",
    }


def test_development_allows_write_without_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "dev_auth.db"))
    monkeypatch.setenv("SQLITE_BACKUP_DIR", str(tmp_path / "backups"))

    with TestClient(app) as client:
        response = client.post("/inquiries", json=inquiry_payload())

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_staging_requires_correct_api_key_for_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("INTERNAL_API_KEY", "internal-test-key")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "staging_auth.db"))
    monkeypatch.setenv("SQLITE_BACKUP_DIR", str(tmp_path / "backups"))

    with TestClient(app) as client:
        missing = client.post("/inquiries", json=inquiry_payload())
        wrong = client.post(
            "/inquiries",
            json=inquiry_payload(),
            headers={"X-Internal-API-Key": "wrong-key"},
        )
        correct = client.post(
            "/inquiries",
            json=inquiry_payload(),
            headers={"X-Internal-API-Key": "internal-test-key"},
        )

    assert missing.status_code == 401
    assert wrong.status_code == 403
    assert correct.status_code == 200


def test_production_requires_correct_api_key_for_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("INTERNAL_API_KEY", "production-test-key")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "production_auth.db"))
    monkeypatch.setenv("SQLITE_BACKUP_DIR", str(tmp_path / "backups"))

    init_database()

    with TestClient(app) as client:
        missing = client.post("/inquiries", json=inquiry_payload())
        correct = client.post(
            "/inquiries",
            json=inquiry_payload(),
            headers={"X-Internal-API-Key": "production-test-key"},
        )

    assert missing.status_code == 401
    assert correct.status_code == 200


def test_staging_without_configured_api_key_rejects_write(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "missing_key.db"))
    monkeypatch.setenv("SQLITE_BACKUP_DIR", str(tmp_path / "backups"))

    with TestClient(app) as client:
        response = client.post("/inquiries", json=inquiry_payload())

    assert response.status_code == 403


def test_sensitive_data_masking_service_and_inquiry_query(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "privacy.db"))
    monkeypatch.setenv("SQLITE_BACKUP_DIR", str(tmp_path / "backups"))

    assert PrivacyService.mask_phone("13800000000") == "138****0000"
    assert PrivacyService.mask_id_number("ABC1234567890") == "ABC******7890"
    assert PrivacyService.mask_name("张三") == "张*"
    assert PrivacyService.mask_name("王小明") == "王**"

    with TestClient(app) as client:
        client.post("/inquiries", json=inquiry_payload())
        masked = client.get("/inquiries", params={"mask_sensitive": True}).json()

    inquiry = masked["inquiries"][0]
    assert inquiry["phone"] == "138****0000"
    assert inquiry["customer_name"] == "张*"


def test_audit_log_is_written_and_queryable(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("SQLITE_BACKUP_DIR", str(tmp_path / "backups"))

    headers = {
        "X-Internal-Actor": "tester",
        "X-Request-Id": "REQ-AUDIT-001",
    }
    with TestClient(app) as client:
        order_response = client.post(
            "/orders",
            json={
                "customer_name": "审计客户",
                "destination": "塞班",
                "total_amount": 100,
                "items": [],
            },
            headers=headers,
        )
        order_id = order_response.json()["order"]["id"]
        client.post(
            f"/orders/{order_id}/mock-payment",
            json={"payment_event_id": "PAY-AUDIT-001"},
            headers=headers,
        )
        logs = client.get(
            "/audit-logs",
            params={"module_name": "orders", "actor": "tester"},
        ).json()["audit_logs"]

    operation_types = {log["operation_type"] for log in logs}
    assert "create_order" in operation_types
    assert "mock_payment" in operation_types
    assert all(log["actor"] == "tester" for log in logs)


def test_sqlite_backup_and_restore_scripts(tmp_path):
    db_path = tmp_path / "travel_products.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE audit_rows (value TEXT NOT NULL)")
    conn.execute("INSERT INTO audit_rows VALUES ('original')")
    conn.commit()
    conn.close()
    backup_dir = tmp_path / "backups"

    backup_path = create_backup(
        source_path=db_path,
        backup_dir=backup_dir,
        timestamp="20260101-000000",
    )
    assert backup_path.exists()
    backup_conn = sqlite3.connect(backup_path)
    assert backup_conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert backup_conn.execute("SELECT value FROM audit_rows").fetchone()[0] == "original"
    backup_conn.close()
    second_backup = create_backup(
        source_path=db_path,
        backup_dir=backup_dir,
        timestamp="20260101-000000",
    )
    assert second_backup != backup_path
    assert second_backup.exists()

    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE audit_rows SET value = 'changed'")
    conn.commit()
    conn.close()
    result = restore_backup(
        backup_path=backup_path,
        target_path=db_path,
        backup_dir=backup_dir,
    )

    restored_conn = sqlite3.connect(db_path)
    assert restored_conn.execute("SELECT value FROM audit_rows").fetchone()[0] == "original"
    restored_conn.close()
    assert result["pre_restore_backup"].exists()
    previous_conn = sqlite3.connect(result["pre_restore_backup"])
    assert previous_conn.execute("SELECT value FROM audit_rows").fetchone()[0] == "changed"
    previous_conn.close()


def test_sqlite_backup_includes_committed_wal_data(tmp_path):
    db_path = tmp_path / "wal.db"
    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE audit_rows (value TEXT NOT NULL)")
    conn.execute("INSERT INTO audit_rows VALUES ('committed-in-wal')")
    conn.commit()
    assert (tmp_path / "wal.db-wal").exists()

    backup_path = create_backup(
        source_path=db_path,
        backup_dir=tmp_path / "backups",
        timestamp="20260101-000000",
    )

    backup_conn = sqlite3.connect(backup_path)
    assert backup_conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert backup_conn.execute("SELECT value FROM audit_rows").fetchone()[0] == "committed-in-wal"
    backup_conn.close()
    conn.close()


def test_invalid_restore_backup_does_not_overwrite_target(tmp_path):
    db_path = tmp_path / "target.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE audit_rows (value TEXT NOT NULL)")
    conn.execute("INSERT INTO audit_rows VALUES ('keep-me')")
    conn.commit()
    conn.close()
    original_bytes = db_path.read_bytes()

    invalid_backup = tmp_path / "invalid.sqlite3"
    invalid_backup.write_text("not-a-sqlite-database", encoding="utf-8")

    with pytest.raises(ValueError, match="not a valid SQLite database"):
        restore_backup(
            backup_path=invalid_backup,
            target_path=db_path,
            backup_dir=tmp_path / "backups",
        )

    assert db_path.read_bytes() == original_bytes
    target_conn = sqlite3.connect(db_path)
    assert target_conn.execute("SELECT value FROM audit_rows").fetchone()[0] == "keep-me"
    target_conn.close()
    assert not (tmp_path / "backups").exists()


def test_readiness_includes_security_and_backup_checks(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("INTERNAL_API_KEY", "readiness-key")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "readiness.db"))
    monkeypatch.setenv("SQLITE_BACKUP_DIR", str(tmp_path / "backups"))

    with TestClient(app) as client:
        readiness = client.get("/system-health/readiness").json()
        security = client.get("/system-health/security").json()
        backup = client.get("/system-health/backup").json()

    assert readiness["app_env"] == "staging"
    assert readiness["security_config_ok"] is True
    assert readiness["backup_directory_ok"] is True
    assert "security_config_ok" in readiness
    assert security["internal_api_key_configured"] is True
    assert backup["backup_directory_ok"] is True
