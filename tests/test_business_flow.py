from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from apps.backend.main import app


def test_customer_inquiry_recommendation_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "travel_test.db"))
    last_contact_at = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    next_follow_up_at = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")

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
            "message": "想咨询北京5日游",
            "source": "小红书",
            "assigned_sales": "王销售",
            "priority": "high",
            "last_contact_at": last_contact_at,
            "next_follow_up_at": next_follow_up_at
        }
        inquiry_response = client.post("/inquiries", json=inquiry_payload)
        assert inquiry_response.status_code == 200
        inquiry_body = inquiry_response.json()
        assert inquiry_body["success"] is True
        inquiry_id = inquiry_body["inquiry_id"]

        invalid_priority_response = client.post(
            "/inquiries",
            json={**inquiry_payload, "customer_name": "错误优先级客户", "priority": "urgent"}
        )
        assert invalid_priority_response.status_code == 422

        inquiries_response = client.get("/inquiries")
        assert inquiries_response.status_code == 200
        assert inquiries_response.json()["count"] == 1

        filtered_response = client.get(
            "/inquiries",
            params={
                "follow_status": "new",
                "assigned_sales": "王销售",
                "priority": "high",
                "source": "小红书",
                "next_follow_up_before": datetime.now().isoformat(timespec="seconds")
            }
        )
        assert filtered_response.status_code == 200
        assert filtered_response.json()["count"] == 1

        today_follow_up_response = client.get("/inquiries/follow-up/today")
        assert today_follow_up_response.status_code == 200
        today_follow_up_body = today_follow_up_response.json()
        assert today_follow_up_body["count"] == 1
        assert today_follow_up_body["inquiries"][0]["id"] == inquiry_id

        detail_response = client.get(f"/inquiries/{inquiry_id}")
        assert detail_response.status_code == 200
        detail_body = detail_response.json()
        assert detail_body["inquiry"]["destination"] == "北京"
        assert detail_body["inquiry"]["source"] == "小红书"
        assert detail_body["inquiry"]["assigned_sales"] == "王销售"
        assert detail_body["inquiry"]["priority"] == "high"
        assert detail_body["inquiry"]["last_contact_at"] == last_contact_at
        assert detail_body["inquiry"]["next_follow_up_at"] == next_follow_up_at

        missing_detail_response = client.get("/inquiries/99999")
        assert missing_detail_response.status_code == 404

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

        missing_recommendation_response = client.get("/inquiries/99999/recommendations")
        assert missing_recommendation_response.status_code == 404

        status_response = client.patch(
            f"/inquiries/{inquiry_id}/status",
            json={"follow_status": "contacted"}
        )
        assert status_response.status_code == 200
        assert status_response.json()["inquiry"]["follow_status"] == "contacted"
        assert status_response.json()["inquiry"]["assigned_sales"] == "王销售"

        missing_status_response = client.patch(
            "/inquiries/99999/status",
            json={"follow_status": "contacted"}
        )
        assert missing_status_response.status_code == 404


def test_inquiry_crm_fields_use_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "travel_test.db"))

    with TestClient(app) as client:
        response = client.post(
            "/inquiries",
            json={
                "customer_name": "默认字段客户",
                "message": "想了解周边游"
            }
        )
        assert response.status_code == 200

        inquiry_id = response.json()["inquiry_id"]
        detail_response = client.get(f"/inquiries/{inquiry_id}")
        assert detail_response.status_code == 200

        inquiry = detail_response.json()["inquiry"]
        assert inquiry["source"] == "未知"
        assert inquiry["assigned_sales"] == "未分配"
        assert inquiry["priority"] == "medium"
        assert inquiry["last_contact_at"] is None
        assert inquiry["next_follow_up_at"] is None


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
