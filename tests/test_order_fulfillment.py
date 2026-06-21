from fastapi.testclient import TestClient

from apps.backend.main import app


def test_order_transaction_and_fulfillment_center_mvp(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "order_mvp.db"))

    with TestClient(app) as client:
        resource_response = client.post(
            "/resources/transport",
            json={
                "destination": "泰国",
                "resource_name": "深圳往返曼谷机票",
                "supplier_name": "测试供应商",
                "transport_type": "flight",
                "departure_city": "深圳",
                "arrival_city": "曼谷",
                "cost_price": 1000,
                "sale_price": 1300,
                "stock_quantity": 3,
            },
        )
        assert resource_response.status_code == 200
        resource_id = resource_response.json()["resource"]["id"]

        create_response = client.post(
            "/orders",
            json={
                "customer_name": "订单客户",
                "phone": "13800000000",
                "destination": "泰国",
                "people_count": 2,
                "items": [
                    {
                        "resource_type": "transport",
                        "resource_id": resource_id,
                        "quantity": 2,
                    }
                ],
            },
        )
        assert create_response.status_code == 200
        order = create_response.json()["order"]
        order_id = order["id"]
        assert order["order_no"].startswith("ORD-")
        assert order["order_status"] == "pending_payment"
        assert order["payment_status"] == "unpaid"
        assert order["fulfillment_status"] == "pending"
        assert order["total_amount"] == 2600
        assert order["paid_amount"] == 0
        assert order["items"][0]["total_price"] == 2600

        reserved_resource = client.get("/resources/transport").json()["resources"][0]
        assert reserved_resource["reserved_quantity"] == 2
        assert reserved_resource["sold_quantity"] == 0
        assert reserved_resource["available_quantity"] == 1

        insufficient_response = client.post(
            "/orders",
            json={
                "customer_name": "库存不足客户",
                "destination": "泰国",
                "people_count": 2,
                "items": [
                    {
                        "resource_type": "transport",
                        "resource_id": resource_id,
                        "quantity": 2,
                    }
                ],
            },
        )
        assert insufficient_response.status_code == 400
        assert insufficient_response.json()["detail"] == "库存不足"
        assert client.get("/orders").json()["count"] == 1

        inactive_product_response = client.post(
            "/insurance-products",
            json={
                "name": "停用保险",
                "provider": "测试保险公司",
                "coverage_summary": "仅用于状态校验",
                "price": 99,
                "status": "inactive",
            },
        )
        inactive_product_id = inactive_product_response.json()[
            "insurance_product"
        ]["id"]
        inactive_selection = client.post(
            f"/orders/{order_id}/insurances",
            json={
                "insurance_product_id": inactive_product_id,
                "insured_customer_name": "订单客户",
            },
        )
        assert inactive_selection.status_code == 400

        active_product_response = client.post(
            "/insurance-products",
            json={
                "name": "境外旅行保险",
                "provider": "测试保险公司",
                "coverage_summary": "MVP 保障摘要记录",
                "price": 128,
                "status": "active",
            },
        )
        active_product_id = active_product_response.json()[
            "insurance_product"
        ]["id"]
        insurance_response = client.post(
            f"/orders/{order_id}/insurances",
            json={
                "insurance_product_id": active_product_id,
                "insured_customer_name": "订单客户",
            },
        )
        assert insurance_response.status_code == 200
        assert insurance_response.json()["order_insurance"]["price"] == 128
        assert client.get(f"/orders/{order_id}/insurances").json()["count"] == 1
        assert client.get("/insurance-products", params={"status": "active"}).json()[
            "count"
        ] == 1
        assert client.get(f"/orders/{order_id}").json()["order"][
            "total_amount"
        ] == 2728

        document_response = client.post(
            f"/orders/{order_id}/documents",
            json={
                "customer_name": "订单客户",
                "document_type": "passport",
                "document_number": "TEST-PASSPORT-001",
                "file_name": "passport.jpg",
                "file_url": "/mock/passport.jpg",
            },
        )
        assert document_response.status_code == 200
        document = document_response.json()["document"]
        assert document["ocr_status"] == "pending"
        assert document["ocr_raw_text"] is None
        assert document["verified_status"] == "pending"
        assert client.get(f"/orders/{order_id}/documents").json()["count"] == 1

        contract_response = client.post(
            f"/orders/{order_id}/contracts/generate",
        )
        assert contract_response.status_code == 200
        contract = contract_response.json()["contract"]
        contract_id = contract["id"]
        assert contract["contract_no"].startswith("CTR-")
        assert contract["contract_status"] == "generated"
        assert client.get(f"/orders/{order_id}/contracts").json()["count"] == 1

        reminder_response = client.post(
            f"/orders/{order_id}/reminders",
            json={
                "reminder_type": "departure",
                "title": "出发资料提醒",
                "message": "请人工核对出发资料",
                "remind_at": "2026-07-01T09:00:00",
            },
        )
        assert reminder_response.status_code == 200
        reminder_id = reminder_response.json()["reminder"]["id"]
        assert reminder_response.json()["reminder"]["status"] == "pending"
        assert client.get(f"/orders/{order_id}/reminders").json()["count"] == 1
        reminder_status_response = client.patch(
            f"/orders/{order_id}/reminders/{reminder_id}/status",
            json={"status": "completed"},
        )
        assert reminder_status_response.status_code == 200
        assert reminder_status_response.json()["reminder"]["status"] == "completed"

        payment_response = client.post(f"/orders/{order_id}/mock-payment")
        assert payment_response.status_code == 200
        paid_order = payment_response.json()["order"]
        assert paid_order["payment_status"] == "mock_paid"
        assert paid_order["order_status"] == "paid"
        assert paid_order["paid_amount"] == 2728
        assert paid_order["fulfillment_status"] == "contract_pending"

        paid_resource = client.get("/resources/transport").json()["resources"][0]
        assert paid_resource["reserved_quantity"] == 0
        assert paid_resource["sold_quantity"] == 2
        assert paid_resource["available_quantity"] == 1

        duplicate_payment = client.post(f"/orders/{order_id}/mock-payment")
        assert duplicate_payment.status_code == 409
        duplicate_resource = client.get("/resources/transport").json()["resources"][0]
        assert duplicate_resource["sold_quantity"] == 2

        sign_response = client.post(
            f"/orders/{order_id}/contracts/{contract_id}/mock-sign"
        )
        assert sign_response.status_code == 200
        assert sign_response.json()["contract"]["contract_status"] == "signed"
        assert sign_response.json()["contract"]["signed_at"] is not None
        assert client.get(f"/orders/{order_id}").json()["order"][
            "fulfillment_status"
        ] == "ready_to_travel"

        fulfilling_response = client.patch(
            f"/orders/{order_id}/status",
            json={"order_status": "fulfilling"},
        )
        assert fulfilling_response.status_code == 200
        assert fulfilling_response.json()["order"]["fulfillment_status"] == "in_progress"
        completed_response = client.patch(
            f"/orders/{order_id}/status",
            json={"order_status": "completed"},
        )
        assert completed_response.status_code == 200
        assert completed_response.json()["order"]["fulfillment_status"] == "completed"


def test_unpaid_cancellation_releases_inventory_and_inquiry_order(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "order_cancel.db"))

    with TestClient(app) as client:
        resource_response = client.post(
            "/resources/activities",
            json={
                "destination": "富国岛",
                "resource_name": "海岛活动",
                "supplier_name": "测试地接",
                "activity_type": "island",
                "duration": "半天",
                "suitable_people": "成人",
                "cost_price": 200,
                "sale_price": 300,
                "stock_quantity": 2,
            },
        )
        resource_id = resource_response.json()["resource"]["id"]

        cancel_order_response = client.post(
            "/orders",
            json={
                "customer_name": "待取消客户",
                "destination": "富国岛",
                "people_count": 1,
                "items": [
                    {
                        "resource_type": "activity",
                        "resource_id": resource_id,
                        "quantity": 1,
                        "unit_price": 350,
                    }
                ],
            },
        )
        cancel_order_id = cancel_order_response.json()["order"]["id"]
        reserved = client.get("/resources/activities").json()["resources"][0]
        assert reserved["reserved_quantity"] == 1

        cancel_response = client.patch(
            f"/orders/{cancel_order_id}/status",
            json={"order_status": "cancelled"},
        )
        assert cancel_response.status_code == 200
        assert cancel_response.json()["order"]["order_status"] == "cancelled"
        released = client.get("/resources/activities").json()["resources"][0]
        assert released["reserved_quantity"] == 0
        assert released["sold_quantity"] == 0
        assert client.post(f"/orders/{cancel_order_id}/mock-payment").status_code == 400

        inquiry_response = client.post(
            "/inquiries",
            json={
                "customer_name": "咨询转订单客户",
                "phone": "13900000000",
                "destination": "富国岛",
                "people_count": 3,
                "message": "咨询转订单测试",
            },
        )
        inquiry_id = inquiry_response.json()["inquiry_id"]
        inquiry_order_response = client.post(
            "/orders",
            json={"inquiry_id": inquiry_id, "total_amount": 5000},
        )
        assert inquiry_order_response.status_code == 200
        inquiry_order = inquiry_order_response.json()["order"]
        assert inquiry_order["inquiry_id"] == inquiry_id
        assert inquiry_order["customer_name"] == "咨询转订单客户"
        assert inquiry_order["people_count"] == 3
        assert inquiry_order["total_amount"] == 5000
        filtered = client.get("/orders", params={"inquiry_id": inquiry_id})
        assert filtered.status_code == 200
        assert filtered.json()["count"] == 1
