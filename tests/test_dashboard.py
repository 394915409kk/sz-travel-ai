from fastapi.testclient import TestClient

from apps.backend.main import app


def test_dashboard_overview_today_sales_profit_risks_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "dashboard.db"))
    with TestClient(app) as client:
        client.post("/inquiries", json={"customer_name": "驾驶舱客户", "destination": "北京", "message": "驾驶舱测试"})
        client.post("/orders", json={"customer_name": "驾驶舱客户", "destination": "北京", "total_amount": 500, "items": []})
        overview = client.get("/dashboard/overview")
        assert overview.status_code == 200
        body = overview.json()
        assert body["leads_summary"]["today"] == 1
        assert body["order_summary"]["today"] == 1
        assert body["revenue_summary"]["today_sales"] == 500
        assert body["profit_summary"]["today_gross_margin"] == 1.0
        assert body["risk_summary"]["risk_orders"] == 1
        today = client.get("/dashboard/today").json()
        assert today["today_orders"] == 1
        assert client.get("/dashboard/sales").status_code == 200
        assert client.get("/dashboard/profit").json()["summary"]["total_revenue"] == 500
        assert client.get("/dashboard/risks").json()["summary"]["risk_orders"] == 1
        actions = client.get("/dashboard/actions").json()
        assert actions["count"] >= 1
