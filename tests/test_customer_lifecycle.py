from datetime import date, timedelta

from fastapi.testclient import TestClient

from apps.backend.db import get_connection
from apps.backend.main import app


def _order(client, name, amount):
    return client.post("/orders", json={"customer_name": name, "phone": "13900000000", "destination": "北京", "people_count": 1, "total_amount": amount, "items": []}).json()["order"]


def test_generate_high_value_profile_and_repurchase_task(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "lifecycle.db"))
    with TestClient(app) as client:
        _order(client, "高价值客户", 12000)
        profiles = client.post("/customer-lifecycle/profiles/generate").json()["profiles"]
        assert len(profiles) == 1
        profile = profiles[0]
        assert profile["customer_level"] == "high_value"
        assert profile["total_spent"] == 12000
        assert client.get("/customer-lifecycle/high-value-customers").json()["count"] == 1
        assert client.get(f"/customer-lifecycle/profiles/{profile['id']}").status_code == 200
        tasks = client.post("/customer-lifecycle/repurchase-tasks/generate").json()["tasks"]
        assert len(tasks) == 1
        updated = client.patch(f"/customer-lifecycle/repurchase-tasks/{tasks[0]['id']}/status", json={"status": "completed"}).json()["task"]
        assert updated["completed_at"] is not None


def test_dormant_customer_is_identified(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "dormant.db"))
    with TestClient(app) as client:
        order = _order(client, "沉睡客户", 2000)
        old_date = (date.today() - timedelta(days=220)).isoformat()
        conn = get_connection()
        conn.execute("UPDATE orders SET created_at = ? WHERE id = ?", (f"{old_date}T10:00:00", order["id"]))
        conn.commit()
        conn.close()
        profile = client.post("/customer-lifecycle/profiles/generate").json()["profiles"][0]
        assert profile["lifecycle_stage"] == "dormant"
        assert "CUSTOMER_DORMANT_RISK" in profile["risk_flags"]
        assert client.get("/customer-lifecycle/dormant-customers").json()["count"] == 1
