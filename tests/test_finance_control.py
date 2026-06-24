from datetime import date, timedelta

from fastapi.testclient import TestClient

from apps.backend.db import get_connection
from apps.backend.main import app


def _order_with_cost(client):
    resource = client.post("/resources/activities", json={
        "destination": "塞班", "resource_name": "财务资源", "supplier_name": "财务供应商",
        "activity_type": "tour", "duration": "半天", "suitable_people": "成人",
        "cost_price": 400, "sale_price": 1000, "stock_quantity": 5,
    }).json()["resource"]
    return client.post("/orders", json={
        "customer_name": "财务客户", "destination": "塞班",
        "items": [{"resource_type": "activity", "resource_id": resource["id"], "quantity": 1}],
    }).json()["order"]


def test_generate_query_update_and_reconciliation(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "finance.db"))
    with TestClient(app) as client:
        order = _order_with_cost(client)
        generated = client.post("/finance-control/records/generate", json={"order_id": order["id"]}).json()
        assert generated["generated_count"] == 2
        assert {row["record_type"] for row in generated["records"]} == {"receivable", "supplier_cost"}
        assert client.post("/finance-control/records/generate", json={"order_id": order["id"]}).json()["generated_count"] == 0
        payable = next(row for row in generated["records"] if row["direction"] == "expense")
        updated = client.patch(f"/finance-control/records/{payable['id']}/status", json={"status": "paid"}).json()["record"]
        assert updated["paid_at"] is not None
        report = client.get("/finance-control/reconciliation-report").json()["report"]
        assert report["total_receivable"] == 1000
        assert report["total_payable"] == 400
        assert report["gross_profit"] == 600


def test_overdue_record_and_risk_alert(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "finance_overdue.db"))
    with TestClient(app) as client:
        order = _order_with_cost(client)
        client.post("/finance-control/records/generate", json={"order_id": order["id"]})
        conn = get_connection()
        conn.execute("UPDATE finance_records SET due_date = ? WHERE record_type = 'receivable'", ((date.today() - timedelta(days=1)).isoformat(),))
        conn.commit()
        conn.close()
        overdue = client.get("/finance-control/overdue").json()
        assert overdue["count"] == 1
        assert "FINANCE_RECONCILIATION_RISK" in overdue["records"][0]["risk_flags"]
        alerts = client.get("/finance-control/risk-alerts").json()
        assert alerts["count"] == 1
        assert alerts["alerts"][0]["amount"] == 1000


def test_receivable_syncs_after_mock_payment_without_duplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "finance_payment_sync.db"))
    with TestClient(app) as client:
        order = _order_with_cost(client)
        client.post("/finance-control/records/generate", json={"order_id": order["id"]})
        payment = client.post(f"/orders/{order['id']}/mock-payment", json={"payment_event_id": "PAY-FINANCE-SYNC"})
        assert payment.status_code == 200
        regenerated = client.post("/finance-control/records/generate", json={"order_id": order["id"]})
        assert regenerated.json()["generated_count"] == 0
        receivables = client.get("/finance-control/records", params={"record_type": "receivable"}).json()["records"]
        assert len(receivables) == 1
        assert receivables[0]["status"] == "paid"
        assert receivables[0]["paid_at"] is not None
