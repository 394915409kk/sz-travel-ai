from datetime import date

from fastapi.testclient import TestClient

from apps.backend.db import get_connection
from apps.backend.main import app


def create_activity_resource(
    client,
    destination="富国岛",
    cost_price=600,
    sale_price=1000,
    stock_quantity=20,
):
    response = client.post(
        "/resources/activities",
        json={
            "destination": destination,
            "resource_name": f"{destination}利润测试活动",
            "supplier_name": "利润测试供应商",
            "activity_type": "island",
            "duration": "半天",
            "suitable_people": "成人",
            "cost_price": cost_price,
            "sale_price": sale_price,
            "stock_quantity": stock_quantity,
        },
    )
    assert response.status_code == 200
    return response.json()["resource"]["id"]


def create_order(
    client,
    resource_id=None,
    destination="富国岛",
    quantity=1,
    unit_price=None,
    total_amount=None,
    inquiry_id=None,
    customer_name="利润测试客户",
):
    payload = {
        "destination": destination,
        "people_count": quantity,
        "items": [],
    }
    if inquiry_id is None:
        payload["customer_name"] = customer_name
    else:
        payload = {"inquiry_id": inquiry_id, "items": []}
    if resource_id is not None:
        item = {
            "resource_type": "activity",
            "resource_id": resource_id,
            "quantity": quantity,
        }
        if unit_price is not None:
            item["unit_price"] = unit_price
        payload["items"].append(item)
    if total_amount is not None:
        payload["total_amount"] = total_amount

    response = client.post("/orders", json=payload)
    assert response.status_code == 200
    return response.json()["order"]


def pay_order(client, order_id, event_suffix):
    response = client.post(
        f"/orders/{order_id}/mock-payment",
        json={"payment_event_id": f"PAY-PROFIT-{event_suffix}"},
    )
    assert response.status_code == 200
    return response.json()["order"]


def test_paid_order_profit_calculation_includes_insurance(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "paid_profit.db"))

    with TestClient(app) as client:
        resource_id = create_activity_resource(client)
        order = create_order(client, resource_id=resource_id, quantity=2)

        insurance_product = client.post(
            "/insurance-products",
            json={
                "name": "利润测试保险",
                "provider": "测试保险公司",
                "price": 100,
                "status": "active",
            },
        ).json()["insurance_product"]
        insurance_response = client.post(
            f"/orders/{order['id']}/insurances",
            json={
                "insurance_product_id": insurance_product["id"],
                "insured_customer_name": "利润测试客户",
            },
        )
        assert insurance_response.status_code == 200
        pay_order(client, order["id"], "PAID")

        response = client.get(f"/profit/orders/{order['id']}")
        assert response.status_code == 200
        profit = response.json()
        assert profit["order_id"] == order["id"]
        assert profit["order_revenue"] == 2100
        assert profit["resource_cost"] == 1200
        assert profit["insurance_revenue"] == 100
        assert profit["gross_profit"] == 900
        assert profit["gross_margin"] == 0.4286
        assert profit["profit_level"] == "high_profit"
        assert profit["risk_flags"] == []


def test_profit_risks_cover_unpaid_cancelled_missing_cost_and_zero_revenue(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "profit_risks.db"))

    with TestClient(app) as client:
        resource_id = create_activity_resource(client, cost_price=200, sale_price=300)
        unpaid_order = create_order(client, resource_id=resource_id)
        unpaid_profit = client.get(
            f"/profit/orders/{unpaid_order['id']}"
        ).json()
        assert "unpaid_order" in unpaid_profit["risk_flags"]

        cancel_response = client.patch(
            f"/orders/{unpaid_order['id']}/status",
            json={"order_status": "cancelled"},
        )
        assert cancel_response.status_code == 200
        cancelled_profit = client.get(
            f"/profit/orders/{unpaid_order['id']}"
        ).json()
        assert "cancelled_order" in cancelled_profit["risk_flags"]
        assert "unpaid_order" in cancelled_profit["risk_flags"]

        zero_order = create_order(client, total_amount=0)
        zero_profit = client.get(f"/profit/orders/{zero_order['id']}").json()
        assert zero_profit["gross_margin"] == 0.0
        assert zero_profit["profit_level"] == "low_profit"
        assert "low_margin" in zero_profit["risk_flags"]
        assert "missing_resource_cost" in zero_profit["risk_flags"]

        missing_resource_id = create_activity_resource(
            client,
            destination="塞班",
            cost_price=500,
            sale_price=800,
        )
        missing_cost_order = create_order(
            client,
            resource_id=missing_resource_id,
            destination="塞班",
        )
        conn = get_connection()
        conn.execute(
            "DELETE FROM activity_resources WHERE id = ?",
            (missing_resource_id,),
        )
        conn.commit()
        conn.close()

        missing_cost_profit = client.get(
            f"/profit/orders/{missing_cost_order['id']}"
        ).json()
        assert "missing_resource_cost" in missing_cost_profit["risk_flags"]
        assert "补齐订单资源和成本价" in missing_cost_profit["recommendation"]


def test_profit_summary_high_profit_risk_and_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "profit_summary.db"))

    with TestClient(app) as client:
        high_resource_id = create_activity_resource(
            client,
            destination="塞班",
            cost_price=100,
            sale_price=500,
        )
        inquiry = client.post(
            "/inquiries",
            json={
                "customer_name": "高利润客户",
                "destination": "塞班",
                "people_count": 2,
                "message": "利润汇总测试",
                "assigned_sales": "张销售",
            },
        ).json()
        high_order = create_order(
            client,
            resource_id=high_resource_id,
            quantity=2,
            inquiry_id=inquiry["inquiry_id"],
        )
        pay_order(client, high_order["id"], "HIGH")

        low_resource_id = create_activity_resource(
            client,
            destination="富国岛",
            cost_price=95,
            sale_price=100,
        )
        low_order = create_order(
            client,
            resource_id=low_resource_id,
            unit_price=100,
        )

        summary = client.get("/profit/summary").json()
        assert summary["total_orders"] == 2
        assert summary["paid_orders"] == 1
        assert summary["cancelled_orders"] == 0
        assert summary["total_revenue"] == 1100
        assert summary["total_resource_cost"] == 295
        assert summary["total_gross_profit"] == 805
        assert summary["average_margin"] == 0.7318
        assert summary["high_profit_orders"] == 1
        assert summary["low_profit_orders"] == 1
        assert summary["loss_orders"] == 0

        high_profit = client.get("/profit/orders/high-profit").json()
        assert high_profit["count"] == 1
        assert high_profit["orders"][0]["order_id"] == high_order["id"]

        risk = client.get("/profit/orders/risk").json()
        assert risk["count"] == 1
        assert risk["orders"][0]["order_id"] == low_order["id"]

        paid_summary = client.get(
            "/profit/summary",
            params={"payment_status": "mock_paid"},
        ).json()
        assert paid_summary["total_orders"] == 1
        assert paid_summary["total_revenue"] == 1000

        sales_summary = client.get(
            "/profit/summary",
            params={"sales": "张销售", "date_from": date.today().isoformat()},
        ).json()
        assert sales_summary["total_orders"] == 1
        assert sales_summary["total_revenue"] == 1000


def test_ceo_agent_report_alerts_and_recommendations(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "ceo_agent.db"))

    with TestClient(app) as client:
        high_resource_id = create_activity_resource(
            client,
            destination="塞班",
            cost_price=100,
            sale_price=500,
        )
        high_order = create_order(client, resource_id=high_resource_id, quantity=2)
        pay_order(client, high_order["id"], "CEO-HIGH")

        loss_resource_id = create_activity_resource(
            client,
            destination="富国岛",
            cost_price=200,
            sale_price=300,
        )
        loss_order = create_order(
            client,
            resource_id=loss_resource_id,
            total_amount=100,
        )
        pay_order(client, loss_order["id"], "CEO-LOSS")
        create_order(client, total_amount=0, customer_name="成本缺失客户")

        report_response = client.get("/ceo-agent/daily-report")
        assert report_response.status_code == 200
        report = report_response.json()
        required_fields = {
            "report_date",
            "revenue_summary",
            "profit_summary",
            "order_summary",
            "destination_summary",
            "risk_summary",
            "top_profit_orders",
            "key_findings",
            "action_suggestions",
        }
        assert required_fields <= report.keys()
        assert report["order_summary"]["total_orders"] == 3
        assert report["profit_summary"]["loss_orders"] == 1
        assert report["key_findings"]
        assert report["action_suggestions"]

        alerts_response = client.get("/ceo-agent/risk-alerts")
        assert alerts_response.status_code == 200
        alerts = alerts_response.json()
        alert_types = {alert["risk_type"] for alert in alerts["alerts"]}
        assert alerts["count"] >= 3
        assert {"negative_profit", "unpaid_order", "missing_cost"} <= alert_types

        recommendations_response = client.get("/ceo-agent/recommendations")
        assert recommendations_response.status_code == 200
        recommendations = recommendations_response.json()
        categories = {
            recommendation["category"]
            for recommendation in recommendations["recommendations"]
        }
        assert recommendations["count"] >= 3
        assert {"pricing", "growth", "cost_control", "collection"} <= categories
