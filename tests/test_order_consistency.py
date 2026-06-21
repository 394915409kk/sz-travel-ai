from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient

from apps.backend.db import get_connection
from apps.backend.main import app


def create_activity_resource(client, stock_quantity):
    response = client.post(
        "/resources/activities",
        json={
            "destination": "富国岛",
            "resource_name": "一致性测试活动",
            "supplier_name": "一致性测试供应商",
            "activity_type": "island",
            "duration": "半天",
            "suitable_people": "成人",
            "cost_price": 200,
            "sale_price": 300,
            "stock_quantity": stock_quantity,
        },
    )
    assert response.status_code == 200
    return response.json()["resource"]["id"]


def create_order(client, resource_id, quantity=1, customer_name="一致性客户"):
    response = client.post(
        "/orders",
        json={
            "customer_name": customer_name,
            "destination": "富国岛",
            "people_count": quantity,
            "items": [
                {
                    "resource_type": "activity",
                    "resource_id": resource_id,
                    "quantity": quantity,
                }
            ],
        },
    )
    return response


def get_activity_inventory(client):
    return client.get("/resources/activities").json()["resources"][0]


def assert_inventory_invariant(inventory):
    assert inventory["reserved_quantity"] >= 0
    assert inventory["sold_quantity"] >= 0
    assert (
        inventory["sold_quantity"] + inventory["reserved_quantity"]
        <= inventory["stock_quantity"]
    )


def test_concurrent_order_creation_never_oversells(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "concurrent_order.db"))

    with TestClient(app) as client:
        resource_id = create_activity_resource(client, stock_quantity=3)
        barrier = Barrier(2)

        def submit_order(customer_name):
            barrier.wait()
            return create_order(
                client,
                resource_id,
                quantity=2,
                customer_name=customer_name,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(submit_order, ("并发客户A", "并发客户B"))
            )

        assert sorted(response.status_code for response in responses) == [200, 400]
        inventory = get_activity_inventory(client)
        assert inventory["reserved_quantity"] == 2
        assert inventory["sold_quantity"] == 0
        assert inventory["available_quantity"] == 1
        assert_inventory_invariant(inventory)
        assert client.get("/orders").json()["count"] == 1


def test_concurrent_duplicate_payment_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "payment_idempotency.db"))

    with TestClient(app) as client:
        resource_id = create_activity_resource(client, stock_quantity=2)
        order_response = create_order(client, resource_id)
        order_id = order_response.json()["order"]["id"]
        barrier = Barrier(2)

        def submit_payment(_):
            barrier.wait()
            return client.post(
                f"/orders/{order_id}/mock-payment",
                json={"payment_event_id": "PAY-CONCURRENT-001"},
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(submit_payment, range(2)))

        assert [response.status_code for response in responses] == [200, 200]
        replay_flags = sorted(
            response.json()["idempotent_replay"] for response in responses
        )
        assert replay_flags == [False, True]

        inventory = get_activity_inventory(client)
        assert inventory["reserved_quantity"] == 0
        assert inventory["sold_quantity"] == 1
        assert_inventory_invariant(inventory)

        second_event_response = client.post(
            f"/orders/{order_id}/mock-payment",
            json={"payment_event_id": "PAY-CONCURRENT-002"},
        )
        assert second_event_response.status_code == 200
        assert second_event_response.json()["idempotent_replay"] is True
        assert get_activity_inventory(client)["sold_quantity"] == 1

        conn = get_connection()
        event_count = conn.execute(
            "SELECT COUNT(*) FROM payment_events WHERE order_id = ?",
            (order_id,),
        ).fetchone()[0]
        conn.close()
        assert event_count == 2


def test_cancel_and_payment_race_has_one_consistent_winner(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "cancel_payment_race.db"))

    with TestClient(app) as client:
        resource_id = create_activity_resource(client, stock_quantity=1)
        order_id = create_order(client, resource_id).json()["order"]["id"]
        barrier = Barrier(2)

        def cancel_order():
            barrier.wait()
            return client.patch(
                f"/orders/{order_id}/status",
                json={"order_status": "cancelled"},
            )

        def pay_order():
            barrier.wait()
            return client.post(
                f"/orders/{order_id}/mock-payment",
                json={"payment_event_id": "PAY-RACE-001"},
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            cancel_future = executor.submit(cancel_order)
            payment_future = executor.submit(pay_order)
            responses = [cancel_future.result(), payment_future.result()]

        assert sorted(response.status_code for response in responses) == [200, 400]
        order = client.get(f"/orders/{order_id}").json()["order"]
        inventory = get_activity_inventory(client)
        assert inventory["reserved_quantity"] == 0
        assert_inventory_invariant(inventory)

        if order["order_status"] == "cancelled":
            assert order["payment_status"] == "unpaid"
            assert inventory["sold_quantity"] == 0
        else:
            assert order["order_status"] == "paid"
            assert order["payment_status"] == "mock_paid"
            assert inventory["sold_quantity"] == 1


def test_amount_freeze_contract_isolation_and_state_machine(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "amount_state.db"))

    with TestClient(app) as client:
        resource_id = create_activity_resource(client, stock_quantity=2)
        order_id = create_order(client, resource_id).json()["order"]["id"]

        illegal_jump = client.patch(
            f"/orders/{order_id}/status",
            json={"order_status": "completed"},
        )
        assert illegal_jump.status_code == 400
        direct_paid = client.patch(
            f"/orders/{order_id}/status",
            json={"order_status": "paid"},
        )
        assert direct_paid.status_code == 400

        insurance_product = client.post(
            "/insurance-products",
            json={
                "name": "一致性测试保险",
                "provider": "测试保险公司",
                "coverage_summary": "测试保障",
                "price": 50,
                "status": "active",
            },
        ).json()["insurance_product"]
        pre_payment_insurance = client.post(
            f"/orders/{order_id}/insurances",
            json={
                "insurance_product_id": insurance_product["id"],
                "insured_customer_name": "一致性客户",
            },
        )
        assert pre_payment_insurance.status_code == 200
        assert client.get(f"/orders/{order_id}").json()["order"][
            "total_amount"
        ] == 350

        payment_response = client.post(
            f"/orders/{order_id}/mock-payment",
            json={"payment_event_id": "PAY-AMOUNT-001"},
        )
        assert payment_response.status_code == 200
        paid_order = payment_response.json()["order"]
        assert paid_order["total_amount"] == 350
        assert paid_order["paid_amount"] == 350

        post_payment_insurance = client.post(
            f"/orders/{order_id}/insurances",
            json={
                "insurance_product_id": insurance_product["id"],
                "insured_customer_name": "一致性客户",
            },
        )
        assert post_payment_insurance.status_code == 400
        frozen_order = client.get(f"/orders/{order_id}").json()["order"]
        assert frozen_order["total_amount"] == 350
        assert frozen_order["paid_amount"] == 350

        inventory_before_contract = get_activity_inventory(client)
        contract = client.post(
            f"/orders/{order_id}/contracts/generate"
        ).json()["contract"]
        sign_response = client.post(
            f"/orders/{order_id}/contracts/{contract['id']}/mock-sign"
        )
        assert sign_response.status_code == 200
        inventory_after_contract = get_activity_inventory(client)
        assert inventory_after_contract == inventory_before_contract
        assert_inventory_invariant(inventory_after_contract)

        paid_cancel = client.patch(
            f"/orders/{order_id}/status",
            json={"order_status": "cancelled"},
        )
        assert paid_cancel.status_code == 400
        assert get_activity_inventory(client)["sold_quantity"] == 1

        fulfilling = client.patch(
            f"/orders/{order_id}/status",
            json={"order_status": "fulfilling"},
        )
        assert fulfilling.status_code == 200
        completed = client.patch(
            f"/orders/{order_id}/status",
            json={"order_status": "completed"},
        )
        assert completed.status_code == 200
        terminal_cancel = client.patch(
            f"/orders/{order_id}/status",
            json={"order_status": "cancelled"},
        )
        assert terminal_cancel.status_code == 400
