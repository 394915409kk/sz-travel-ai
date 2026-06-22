from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient

from apps.backend.main import app


def create_activity_resource(
    client,
    *,
    destination="富国岛",
    resource_name="报价测试活动",
    cost_price=100,
    sale_price=120,
    stock_quantity=10,
    available_start_date=None,
    available_end_date=None,
):
    response = client.post(
        "/resources/activities",
        json={
            "destination": destination,
            "resource_name": resource_name,
            "supplier_name": "报价测试供应商",
            "activity_type": "island",
            "duration": "半天",
            "suitable_people": "成人",
            "cost_price": cost_price,
            "sale_price": sale_price,
            "stock_quantity": stock_quantity,
            "available_start_date": available_start_date,
            "available_end_date": available_end_date,
        },
    )
    assert response.status_code == 200
    return response.json()["resource"]


def generate_quote(
    client,
    resource_id,
    *,
    customer_name="报价客户",
    destination="富国岛",
    quantity=1,
    customer_budget=None,
    target_margin=0.25,
    departure_date=None,
):
    payload = {
        "customer_name": customer_name,
        "destination": destination,
        "people_count": quantity,
        "target_margin": target_margin,
        "resource_items": [
            {
                "resource_type": "activity",
                "resource_id": resource_id,
                "quantity": quantity,
            }
        ],
        "pricing_strategy": "mixed",
    }
    if customer_budget is not None:
        payload["customer_budget"] = customer_budget
    if departure_date is not None:
        payload["departure_date"] = departure_date
    response = client.post("/quotes/generate", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["quote"]


def get_activity(client):
    response = client.get("/resources/activities")
    assert response.status_code == 200
    return response.json()["resources"][0]


def test_manual_quote_calculation_query_and_profit_preview(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "manual_quote.db"))

    with TestClient(app) as client:
        resource = create_activity_resource(
            client,
            cost_price=100,
            sale_price=120,
            stock_quantity=10,
        )
        quote = generate_quote(client, resource["id"], quantity=2)

        assert quote["quote_no"].startswith("QTE-")
        assert quote["quote_status"] == "draft"
        assert quote["base_cost"] == 200
        assert quote["base_price"] == 266.67
        assert quote["dynamic_adjustment"] == 0
        assert quote["final_price"] == 266.67
        assert quote["estimated_profit"] == 66.67
        assert quote["estimated_margin"] == 0.25
        assert "margin_protection" in quote["risk_flags"]
        assert len(quote["items"]) == 1
        assert quote["items"][0]["total_cost"] == 200
        assert quote["items"][0]["total_price"] == quote["final_price"]

        inventory = get_activity(client)
        assert inventory["reserved_quantity"] == 0
        assert inventory["sold_quantity"] == 0

        listed = client.get(
            "/quotes",
            params={
                "destination": "富国",
                "quote_status": "draft",
                "min_margin": 0.24,
                "max_price": 300,
                "date_from": date.today().isoformat(),
                "date_to": date.today().isoformat(),
            },
        )
        assert listed.status_code == 200
        assert listed.json()["count"] == 1
        assert listed.json()["quotes"][0]["id"] == quote["id"]

        detail = client.get(f"/quotes/{quote['id']}")
        assert detail.status_code == 200
        assert detail.json()["quote"]["items"][0]["resource_id"] == resource["id"]

        preview = client.get(f"/quotes/{quote['id']}/profit-preview")
        assert preview.status_code == 200
        assert preview.json() == {
            "quote_id": quote["id"],
            "quote_no": quote["quote_no"],
            "base_cost": 200,
            "final_price": 266.67,
            "estimated_profit": 66.67,
            "estimated_margin": 0.25,
            "target_margin": 0.25,
            "risk_flags": quote["risk_flags"],
            "recommendation": quote["recommendation"],
        }


def test_inquiry_auto_quote_applies_inventory_departure_and_budget_rules(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "dynamic_quote.db"))
    departure_date = (date.today() + timedelta(days=5)).isoformat()

    with TestClient(app) as client:
        resource = create_activity_resource(
            client,
            cost_price=100,
            sale_price=200,
            stock_quantity=2,
            available_start_date=date.today().isoformat(),
            available_end_date=(date.today() + timedelta(days=30)).isoformat(),
        )
        inquiry = client.post(
            "/inquiries",
            json={
                "customer_name": "咨询报价客户",
                "phone": "13900000000",
                "destination": "富国岛",
                "people_count": 1,
                "budget": 1000,
                "departure_date": departure_date,
                "message": "需要自动报价",
            },
        ).json()

        response = client.post(
            "/quotes/generate",
            json={
                "inquiry_id": inquiry["inquiry_id"],
                "target_margin": 0.2,
                "pricing_strategy": "inventory_based",
            },
        )
        assert response.status_code == 200, response.text
        quote = response.json()["quote"]
        assert quote["customer_name"] == "咨询报价客户"
        assert quote["phone"] == "13900000000"
        assert quote["customer_budget"] == 1000
        assert quote["departure_date"] == departure_date
        assert quote["items"][0]["resource_id"] == resource["id"]
        assert quote["base_price"] == 200
        assert quote["dynamic_adjustment"] == 46
        assert quote["final_price"] == 246
        assert {
            "low_stock_price_increase",
            "near_departure_price_increase",
            "high_margin_opportunity",
        } <= set(quote["risk_flags"])
        assert get_activity(client)["reserved_quantity"] == 0

        inquiry_filter = client.get(
            "/quotes",
            params={"inquiry_id": inquiry["inquiry_id"]},
        )
        assert inquiry_filter.json()["count"] == 1


def test_budget_margin_and_missing_cost_risk_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "quote_risks.db"))

    with TestClient(app) as client:
        budget_resource = create_activity_resource(
            client,
            resource_name="预算风险资源",
            cost_price=100,
            sale_price=150,
            stock_quantity=10,
        )
        budget_quote = generate_quote(
            client,
            budget_resource["id"],
            customer_budget=100,
            target_margin=0.2,
        )
        assert budget_quote["final_price"] == 150
        assert "over_customer_budget" in budget_quote["risk_flags"]
        assert "调整资源方案" in budget_quote["recommendation"]

        zero_resource = create_activity_resource(
            client,
            resource_name="待补成本资源",
            cost_price=0,
            sale_price=0,
            stock_quantity=10,
        )
        missing_cost_quote = generate_quote(
            client,
            zero_resource["id"],
            customer_name="成本待补客户",
            target_margin=0.3,
        )
        assert missing_cost_quote["base_cost"] == 0
        assert missing_cost_quote["estimated_margin"] == 0
        assert "missing_resource_cost" in missing_cost_quote["risk_flags"]
        assert "below_target_margin" in missing_cost_quote["risk_flags"]

        no_stock = client.post(
            "/quotes/generate",
            json={
                "customer_name": "库存不足客户",
                "destination": "富国岛",
                "people_count": 11,
                "resource_items": [
                    {
                        "resource_type": "activity",
                        "resource_id": budget_resource["id"],
                        "quantity": 11,
                    }
                ],
            },
        )
        assert no_stock.status_code == 400
        assert "no_available_resource" in no_stock.json()["detail"]["risk_flags"]


def test_quote_status_and_conversion_support_proposed_and_accepted(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "quote_conversion.db"))

    with TestClient(app) as client:
        for index, status in enumerate(("proposed", "accepted"), start=1):
            resource = create_activity_resource(
                client,
                resource_name=f"转订单资源{index}",
                cost_price=100,
                sale_price=180,
                stock_quantity=4,
            )
            quote = generate_quote(
                client,
                resource["id"],
                customer_name=f"转订单客户{index}",
                quantity=2,
                target_margin=0.2,
            )
            status_response = client.patch(
                f"/quotes/{quote['id']}/status",
                json={"quote_status": status},
            )
            assert status_response.status_code == 200
            assert status_response.json()["quote"]["quote_status"] == status

            conversion = client.post(
                f"/quotes/{quote['id']}/convert-to-order"
            )
            assert conversion.status_code == 200, conversion.text
            body = conversion.json()
            order = body["order"]
            assert order["total_amount"] == quote["final_price"]
            assert order["order_status"] == "pending_payment"
            assert order["items"][0]["resource_id"] == resource["id"]
            assert body["quote"]["quote_status"] == "converted_to_order"
            assert body["quote"]["converted_order_id"] == order["id"]

            duplicate = client.post(
                f"/quotes/{quote['id']}/convert-to-order"
            )
            assert duplicate.status_code == 409
            rollback_status = client.patch(
                f"/quotes/{quote['id']}/status",
                json={"quote_status": "accepted"},
            )
            assert rollback_status.status_code == 400


def test_rejected_expired_and_inventory_failure_cannot_convert(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "quote_conversion_risks.db"))

    with TestClient(app) as client:
        blocked_resource = create_activity_resource(
            client,
            cost_price=100,
            sale_price=160,
            stock_quantity=10,
        )
        for status in ("rejected", "expired"):
            quote = generate_quote(client, blocked_resource["id"])
            update = client.patch(
                f"/quotes/{quote['id']}/status",
                json={"quote_status": status},
            )
            assert update.status_code == 200
            conversion = client.post(
                f"/quotes/{quote['id']}/convert-to-order"
            )
            assert conversion.status_code == 400

        scarce_resource = create_activity_resource(
            client,
            resource_name="转换时库存不足资源",
            cost_price=100,
            sale_price=180,
            stock_quantity=2,
        )
        quote = generate_quote(
            client,
            scarce_resource["id"],
            customer_name="库存回滚客户",
            quantity=2,
            target_margin=0.2,
        )
        accepted = client.patch(
            f"/quotes/{quote['id']}/status",
            json={"quote_status": "accepted"},
        )
        assert accepted.status_code == 200

        competing_order = client.post(
            "/orders",
            json={
                "customer_name": "抢占库存客户",
                "destination": "富国岛",
                "people_count": 1,
                "items": [
                    {
                        "resource_type": "activity",
                        "resource_id": scarce_resource["id"],
                        "quantity": 1,
                    }
                ],
            },
        )
        assert competing_order.status_code == 200

        before_count = client.get("/orders").json()["count"]
        failed = client.post(f"/quotes/{quote['id']}/convert-to-order")
        assert failed.status_code == 400
        assert "库存不足" in failed.json()["detail"]
        assert client.get("/orders").json()["count"] == before_count
        failed_quote = client.get(f"/quotes/{quote['id']}").json()["quote"]
        assert failed_quote["quote_status"] == "accepted"
        assert failed_quote["converted_order_id"] is None


def test_concurrent_quote_conversion_creates_only_one_order(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "quote_conversion_race.db"))

    with TestClient(app) as client:
        resource = create_activity_resource(
            client,
            resource_name="并发转换资源",
            cost_price=100,
            sale_price=180,
            stock_quantity=3,
        )
        quote = generate_quote(
            client,
            resource["id"],
            customer_name="并发转换客户",
            quantity=2,
            target_margin=0.2,
        )
        proposed = client.patch(
            f"/quotes/{quote['id']}/status",
            json={"quote_status": "proposed"},
        )
        assert proposed.status_code == 200
        barrier = Barrier(2)

        def convert_quote(_):
            barrier.wait()
            return client.post(f"/quotes/{quote['id']}/convert-to-order")

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(convert_quote, range(2)))

        assert sorted(response.status_code for response in responses) == [200, 409]
        assert client.get("/orders").json()["count"] == 1
        converted_quote = client.get(f"/quotes/{quote['id']}").json()["quote"]
        assert converted_quote["quote_status"] == "converted_to_order"
        assert converted_quote["converted_order_id"] is not None
        inventory = get_activity(client)
        assert inventory["reserved_quantity"] == 2
        assert inventory["sold_quantity"] == 0
