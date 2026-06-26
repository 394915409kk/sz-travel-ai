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
    db_path.write_text("original", encoding="utf-8")
    backup_dir = tmp_path / "backups"

    backup_path = create_backup(
        source_path=db_path,
        backup_dir=backup_dir,
        timestamp="20260101-000000",
    )
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == "original"

    db_path.write_text("changed", encoding="utf-8")
    result = restore_backup(
        backup_path=backup_path,
        target_path=db_path,
        backup_dir=backup_dir,
    )

    assert db_path.read_text(encoding="utf-8") == "original"
    assert result["pre_restore_backup"].exists()


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
