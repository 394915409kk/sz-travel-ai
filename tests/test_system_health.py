from datetime import date, timedelta

from fastapi.testclient import TestClient

from apps.backend.db import get_connection
from apps.backend.main import app


def test_system_health_database_modules_and_readiness(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "health.db"))
    with TestClient(app) as client:
        health = client.get("/system-health")
        assert health.status_code == 200
        assert health.json()["database"]["healthy"] is True
        database = client.get("/system-health/database").json()
        assert database["missing_tables"] == []
        modules = client.get("/system-health/modules").json()
        assert modules["healthy"] is True
        assert all(item["registered"] for item in modules["modules"])
        readiness = client.get("/system-health/readiness").json()
        assert readiness["ready"] is True


def test_system_health_identifies_active_stockout_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "health_risk.db"))
    with TestClient(app) as client:
        client.post("/resources/activities", json={
            "destination": "塞班", "resource_name": "健康检查缺货资源", "supplier_name": "供应商",
            "activity_type": "tour", "duration": "半天", "suitable_people": "成人",
            "cost_price": 100, "sale_price": 200, "stock_quantity": 0,
        })
        order = client.post("/orders", json={"customer_name": "健康财务客户", "destination": "塞班", "total_amount": 100, "items": []}).json()["order"]
        client.post("/finance-control/records/generate", json={"order_id": order["id"]})
        conn = get_connection()
        conn.execute("UPDATE finance_records SET due_date = ? WHERE record_type = 'receivable'", ((date.today() - timedelta(days=1)).isoformat(),))
        conn.commit()
        conn.close()
        risks = client.get("/system-health/risks").json()
        assert any(item["risk_type"] == "STOCK_SHORTAGE_RISK" for item in risks["risks"])
        assert any(item["risk_type"] == "FINANCE_RECONCILIATION_RISK" for item in risks["risks"])
        readiness = client.get("/system-health/readiness").json()
        assert readiness["ready"] is True
        assert readiness["warning_count"] >= 1
