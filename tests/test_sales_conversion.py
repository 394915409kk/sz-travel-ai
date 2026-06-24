from datetime import date, timedelta

from fastapi.testclient import TestClient

from apps.backend.main import app


def _create_quote(client, budget=5000, final_resource_price=1000, departure_days=30, priority="high", with_task=True):
    inquiry = client.post("/inquiries", json={
        "customer_name": "成交测试客户", "phone": "13800000000", "destination": "塞班",
        "people_count": 1, "budget": budget, "departure_date": (date.today() + timedelta(days=departure_days)).isoformat(),
        "message": "咨询塞班", "priority": priority, "assigned_sales": "王销售",
        "next_follow_up_at": date.today().isoformat() if with_task else None,
    }).json()
    if with_task:
        client.post("/follow-up-tasks/generate")
    resource = client.post("/resources/activities", json={
        "destination": "塞班", "resource_name": "成交测试资源", "supplier_name": "测试供应商",
        "activity_type": "tour", "duration": "1天", "suitable_people": "成人",
        "cost_price": final_resource_price * 0.6, "sale_price": final_resource_price, "stock_quantity": 10,
    }).json()["resource"]
    return client.post("/quotes/generate", json={
        "inquiry_id": inquiry["inquiry_id"], "resource_items": [{"resource_type": "activity", "resource_id": resource["id"], "quantity": 1}],
    }).json()["quote"]


def test_quote_analysis_high_intent_script_and_stage(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "sales_conversion.db"))
    with TestClient(app) as client:
        quote = _create_quote(client)
        response = client.post("/sales-conversion/analyze", json={"quote_id": quote["id"], "customer_objections": ["关注价格"]})
        assert response.status_code == 200
        record = response.json()["record"]
        assert 0 <= record["conversion_probability"] <= 1
        assert record["conversion_stage"] == "high_intent"
        assert "塞班" in record["follow_up_script"]
        assert client.get("/sales-conversion/high-intent").json()["count"] == 1
        script = client.get(f"/sales-conversion/{record['id']}/follow-up-script").json()
        assert script["next_best_action"]
        updated = client.patch(f"/sales-conversion/{record['id']}/stage", json={"conversion_stage": "negotiating"})
        assert updated.json()["record"]["conversion_stage"] == "negotiating"


def test_low_budget_and_urgent_departure_are_risks(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "sales_conversion_risk.db"))
    with TestClient(app) as client:
        quote = _create_quote(client, budget=100, final_resource_price=1000, departure_days=3, priority="low", with_task=False)
        record = client.post("/sales-conversion/analyze", json={"quote_id": quote["id"]}).json()["record"]
        assert {"BUDGET_TOO_LOW", "PRICE_TOO_HIGH", "URGENT_DEPARTURE", "NO_FOLLOW_UP"}.issubset(record["risk_flags"])
        risks = client.get("/sales-conversion/risk").json()
        assert risks["count"] == 1
        assert risks["records"][0]["id"] == record["id"]
