from fastapi.testclient import TestClient

from apps.backend.main import app


def _resource(client, name, supplier, stock, sold=0):
    return client.post("/resources/activities", json={
        "destination": "塞班", "resource_name": name, "supplier_name": supplier,
        "activity_type": "tour", "duration": "半天", "suitable_people": "成人",
        "cost_price": 100, "sale_price": 300, "stock_quantity": stock, "sold_quantity": sold,
    }).json()["resource"]


def test_supplier_analysis_stockout_slow_moving_and_suggestions(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "supply.db"))
    with TestClient(app) as client:
        _resource(client, "缺货资源", "供应商A", 0)
        _resource(client, "滞销资源", "供应商B", 10)
        result = client.post("/supply-chain/analyze").json()
        assert len(result["suppliers"]) == 2
        stockout = client.get("/supply-chain/stockout-risks").json()
        assert stockout["count"] == 1
        assert stockout["risks"][0]["supplier_name"] == "供应商A"
        slow = client.get("/supply-chain/slow-moving-resources").json()
        assert any(item["resource_name"] == "滞销资源" for item in slow["resources"])
        suggestions = client.get("/supply-chain/procurement-suggestions").json()["suggestions"]
        actions = {item["suggested_action"] for item in suggestions}
        assert {"increase_stock", "reduce_stock"}.issubset(actions)
        updated = client.patch(f"/supply-chain/procurement-suggestions/{suggestions[0]['id']}/status", json={"status": "accepted"}).json()["suggestion"]
        assert updated["status"] == "accepted"
        assert client.get("/supply-chain/suppliers/供应商A").status_code == 200


def test_supplier_order_profit_is_explainable(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "supply_profit.db"))
    with TestClient(app) as client:
        resource = _resource(client, "成交资源", "利润供应商", 5)
        client.post("/orders", json={"customer_name": "采购测试客户", "destination": "塞班", "items": [{"resource_type": "activity", "resource_id": resource["id"], "quantity": 1}]})
        supplier = client.post("/supply-chain/analyze").json()["suppliers"][0]
        assert supplier["total_orders"] == 1
        assert supplier["total_revenue"] == 300
        assert supplier["total_cost"] == 100
        assert supplier["total_profit"] == 200
        assert supplier["average_margin"] == 0.6667
