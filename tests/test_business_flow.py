from fastapi.testclient import TestClient

from apps.backend.main import app


def test_customer_inquiry_recommendation_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "travel_test.db"))

    with TestClient(app) as client:
        products_response = client.get("/products")
        assert products_response.status_code == 200
        products_body = products_response.json()
        assert products_body["success"] is True
        assert products_body["count"] >= 5

        product_response = client.get("/products/1")
        assert product_response.status_code == 200
        assert product_response.json()["success"] is True

        inquiry_payload = {
            "customer_name": "测试客户",
            "phone": "13800000000",
            "destination": "北京",
            "people_count": 2,
            "budget": 5000,
            "departure_date": "2026-07-01",
            "message": "想咨询北京5日游"
        }
        inquiry_response = client.post("/inquiries", json=inquiry_payload)
        assert inquiry_response.status_code == 200
        inquiry_body = inquiry_response.json()
        assert inquiry_body["success"] is True
        inquiry_id = inquiry_body["inquiry_id"]

        inquiries_response = client.get("/inquiries")
        assert inquiries_response.status_code == 200
        assert inquiries_response.json()["count"] == 1

        detail_response = client.get(f"/inquiries/{inquiry_id}")
        assert detail_response.status_code == 200
        assert detail_response.json()["inquiry"]["destination"] == "北京"

        recommendation_response = client.post(
            "/recommendations",
            json={
                "destination": "北京",
                "budget": 5000,
                "message": "想咨询北京5日游"
            }
        )
        assert recommendation_response.status_code == 200
        assert recommendation_response.json()["count"] >= 1

        inquiry_recommendation_response = client.get(
            f"/inquiries/{inquiry_id}/recommendations"
        )
        assert inquiry_recommendation_response.status_code == 200
        assert inquiry_recommendation_response.json()["count"] >= 1

        status_response = client.patch(
            f"/inquiries/{inquiry_id}/status",
            json={"follow_status": "contacted"}
        )
        assert status_response.status_code == 200
        assert status_response.json()["inquiry"]["follow_status"] == "contacted"


def test_ai_strategy_uses_product_route_and_real_product_data(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "travel_test.db"))

    with TestClient(app) as client:
        legacy_response = client.post("/1/ai-collaborative-strategy")
        assert legacy_response.status_code == 404

        response = client.post("/products/1/ai-collaborative-strategy")
        assert response.status_code == 200

        body = response.json()
        assert body["product_id"] == 1
        assert body["destination"] == "北京"
        assert body["copywriting_output"]["primary_headline"].startswith(
            "探索 深圳出发·北京双飞5日游"
        )
