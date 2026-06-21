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
        recommendation_body = recommendation_response.json()
        assert recommendation_body["count"] >= 1
        first_recommendation = recommendation_body["recommendations"][0]
        assert "product" in first_recommendation
        assert "total_score" in first_recommendation
        assert set(first_recommendation["score_detail"]) == {
            "destination_score",
            "budget_score",
            "people_score",
            "departure_date_score",
            "keyword_score"
        }
        assert "recommendation_reason" in first_recommendation

        inquiry_recommendation_response = client.get(
            f"/inquiries/{inquiry_id}/recommendations"
        )
        assert inquiry_recommendation_response.status_code == 200
        inquiry_recommendation_body = inquiry_recommendation_response.json()
        assert inquiry_recommendation_body["count"] >= 1
        assert "total_score" in inquiry_recommendation_body["recommendations"][0]
        assert "score_detail" in inquiry_recommendation_body["recommendations"][0]

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


def test_recommendations_are_sorted_and_use_low_budget_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "travel_test.db"))

    with TestClient(app) as client:
        scored_response = client.post(
            "/recommendations",
            json={
                "people_count": 20,
                "budget": 5000,
                "departure_date": "2026-08-01",
                "message": "公司团建和海岛产品，关注低价"
            }
        )
        assert scored_response.status_code == 200

        scored_recommendations = scored_response.json()["recommendations"]
        assert len(scored_recommendations) >= 2
        scores = [item["total_score"] for item in scored_recommendations]
        assert scores == sorted(scores, reverse=True)
        assert all("score_detail" in item for item in scored_recommendations)
        assert any(
            item["score_detail"]["keyword_score"] > 0
            for item in scored_recommendations
        )

        fallback_response = client.post(
            "/recommendations",
            json={
                "destination": "北京",
                "people_count": 2,
                "budget": 100,
                "departure_date": "2026-07-01",
                "message": "想去北京，预算较低"
            }
        )
        assert fallback_response.status_code == 200

        fallback_body = fallback_response.json()
        assert fallback_body["count"] >= 1
        assert fallback_body["recommendations"][0]["destination"] == "北京"
        assert any(
            "预算或条件存在差异，建议销售人工确认"
            in item["recommendation_reason"]
            for item in fallback_body["recommendations"]
        )


def test_follow_up_task_generation_filters_and_status(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "travel_test.db"))
    past_due_at = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
    future_due_at = (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds")

    with TestClient(app) as client:
        overdue_inquiry_response = client.post(
            "/inquiries",
            json={
                "customer_name": "张三",
                "destination": "泰国",
                "message": "公司团建咨询",
                "assigned_sales": "王销售",
                "priority": "high",
                "next_follow_up_at": past_due_at
            }
        )
        overdue_inquiry_id = overdue_inquiry_response.json()["inquiry_id"]

        future_inquiry_response = client.post(
            "/inquiries",
            json={
                "customer_name": "李四",
                "destination": "北京",
                "message": "亲子游咨询",
                "assigned_sales": "李销售",
                "priority": "low",
                "next_follow_up_at": future_due_at
            }
        )
        future_inquiry_id = future_inquiry_response.json()["inquiry_id"]

        no_due_inquiry_response = client.post(
            "/inquiries",
            json={
                "customer_name": "王五",
                "message": "暂未确定跟进时间",
                "assigned_sales": "王销售"
            }
        )
        assert no_due_inquiry_response.status_code == 200

        generate_response = client.post("/follow-up-tasks/generate")
        assert generate_response.status_code == 200
        generate_body = generate_response.json()
        assert generate_body["generated_count"] == 2
        assert [
            task["inquiry_id"] for task in generate_body["tasks"]
        ] == [overdue_inquiry_id, future_inquiry_id]

        tasks_by_inquiry = {
            task["inquiry_id"]: task for task in generate_body["tasks"]
        }
        overdue_task = tasks_by_inquiry[overdue_inquiry_id]
        overdue_task_id = overdue_task["id"]
        assert overdue_task["assigned_sales"] == "王销售"
        assert overdue_task["priority"] == "high"
        assert overdue_task["task_status"] == "pending"
        assert overdue_task["due_at"] == past_due_at
        assert overdue_task["completed_at"] is None
        assert overdue_task["task_title"] == "跟进客户 张三 - 泰国"
        assert overdue_task["inquiry"]["customer_name"] == "张三"

        duplicate_response = client.post("/follow-up-tasks/generate")
        assert duplicate_response.status_code == 200
        assert duplicate_response.json()["generated_count"] == 0

        sales_filter_response = client.get(
            "/follow-up-tasks",
            params={"assigned_sales": "王销售"}
        )
        assert sales_filter_response.json()["count"] == 1

        status_filter_response = client.get(
            "/follow-up-tasks",
            params={"task_status": "pending"}
        )
        assert status_filter_response.json()["count"] == 2

        priority_filter_response = client.get(
            "/follow-up-tasks",
            params={"priority": "high"}
        )
        assert priority_filter_response.json()["count"] == 1

        due_filter_response = client.get(
            "/follow-up-tasks",
            params={"due_before": datetime.now().isoformat(timespec="seconds")}
        )
        assert due_filter_response.json()["count"] == 1
        assert due_filter_response.json()["tasks"][0]["id"] == overdue_task_id

        today_response = client.get("/follow-up-tasks/today")
        assert today_response.status_code == 200
        assert today_response.json()["count"] == 1
        assert today_response.json()["tasks"][0]["id"] == overdue_task_id

        detail_response = client.get(f"/follow-up-tasks/{overdue_task_id}")
        assert detail_response.status_code == 200
        assert detail_response.json()["task"]["inquiry_id"] == overdue_inquiry_id

        invalid_status_response = client.patch(
            f"/follow-up-tasks/{overdue_task_id}/status",
            json={"task_status": "in_progress"}
        )
        assert invalid_status_response.status_code == 422

        missing_detail_response = client.get("/follow-up-tasks/99999")
        assert missing_detail_response.status_code == 404

        missing_status_response = client.patch(
            "/follow-up-tasks/99999/status",
            json={"task_status": "done"}
        )
        assert missing_status_response.status_code == 404

        done_response = client.patch(
            f"/follow-up-tasks/{overdue_task_id}/status",
            json={"task_status": "done"}
        )
        assert done_response.status_code == 200
        assert done_response.json()["task"]["task_status"] == "done"
        assert done_response.json()["task"]["completed_at"] is not None

        today_after_done_response = client.get("/follow-up-tasks/today")
        assert today_after_done_response.json()["count"] == 0

        regenerate_after_done_response = client.post("/follow-up-tasks/generate")
        assert regenerate_after_done_response.json()["generated_count"] == 0


def test_travel_resource_cost_center_creation_filters_and_validation(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "travel_test.db"))

    transport_payload = {
        "destination": "泰国",
        "resource_name": "深圳往返曼谷机票",
        "supplier_name": "测试航空供应商",
        "transport_type": "flight",
        "departure_city": "深圳",
        "arrival_city": "曼谷",
        "cost_price": 1800,
        "sale_price": 2200,
        "stock_quantity": 10,
        "sold_quantity": 2,
        "reserved_quantity": 3,
        "available_start_date": "2026-07-01",
        "available_end_date": "2026-08-31",
        "available_dates": ["2026-07-01", "2026-07-02"]
    }
    hotel_payload = {
        "destination": "泰国",
        "resource_name": "曼谷市中心酒店豪华房",
        "supplier_name": "测试酒店供应商",
        "hotel_name": "曼谷市中心酒店",
        "room_type": "豪华大床房",
        "breakfast_included": True,
        "max_occupancy": 2,
        "cost_price": 400,
        "sale_price": 600,
        "available_start_date": "2026-07-01",
        "available_end_date": "2026-07-31"
    }
    attraction_payload = {
        "destination": "北京",
        "resource_name": "故宫成人门票",
        "supplier_name": "测试景区供应商",
        "cost_price": 80,
        "sale_price": 120,
        "status": "inactive"
    }
    restaurant_payload = {
        "destination": "泰国",
        "resource_name": "曼谷团队午餐",
        "supplier_name": "测试餐饮供应商",
        "meal_type": "lunch",
        "price_per_person": 100,
        "cost_price": 80,
        "sale_price": 120
    }
    activity_payload = {
        "destination": "泰国",
        "resource_name": "芭提雅海岛潜水",
        "supplier_name": "测试玩乐供应商",
        "activity_type": "diving",
        "duration": "2小时",
        "suitable_people": "12岁以上健康人群",
        "cost_price": 300,
        "sale_price": 450
    }

    with TestClient(app) as client:
        transport_response = client.post(
            "/resources/transport",
            json=transport_payload
        )
        assert transport_response.status_code == 200
        transport = transport_response.json()["resource"]
        assert transport["transport_type"] == "flight"
        assert transport["departure_city"] == "深圳"
        assert transport["arrival_city"] == "曼谷"
        assert transport["currency"] == "CNY"
        assert transport["status"] == "active"
        assert transport["created_at"] is not None
        assert transport["stock_quantity"] == 10
        assert transport["sold_quantity"] == 2
        assert transport["reserved_quantity"] == 3
        assert transport["available_quantity"] == 5
        assert transport["available_dates"] == ["2026-07-01", "2026-07-02"]

        hotel_response = client.post(
            "/resources/hotel-rooms",
            json=hotel_payload
        )
        assert hotel_response.status_code == 200
        hotel = hotel_response.json()["resource"]
        assert hotel["hotel_name"] == "曼谷市中心酒店"
        assert hotel["room_type"] == "豪华大床房"
        assert hotel["breakfast_included"] is True
        assert hotel["max_occupancy"] == 2

        attraction_response = client.post(
            "/resources/attraction-tickets",
            json=attraction_payload
        )
        assert attraction_response.status_code == 200
        attraction = attraction_response.json()["resource"]
        assert attraction["resource_name"] == "故宫成人门票"

        restaurant_response = client.post(
            "/resources/restaurant-meals",
            json=restaurant_payload
        )
        assert restaurant_response.status_code == 200
        restaurant = restaurant_response.json()["resource"]
        assert restaurant["meal_type"] == "lunch"
        assert restaurant["price_per_person"] == 100

        activity_response = client.post(
            "/resources/activities",
            json=activity_payload
        )
        assert activity_response.status_code == 200
        activity = activity_response.json()["resource"]
        assert activity["activity_type"] == "diving"
        assert activity["duration"] == "2小时"
        assert activity["suitable_people"] == "12岁以上健康人群"

        for resource in (transport, hotel, attraction, restaurant, activity):
            assert "stock_quantity" in resource
            assert "sold_quantity" in resource
            assert "reserved_quantity" in resource
            assert "available_quantity" in resource
            assert "available_dates" in resource

        destination_filter = client.get(
            "/resources/transport",
            params={"destination": "泰国"}
        )
        assert destination_filter.json()["count"] == 1
        wrong_destination_filter = client.get(
            "/resources/transport",
            params={"destination": "日本"}
        )
        assert wrong_destination_filter.json()["count"] == 0

        supplier_filter = client.get(
            "/resources/hotel-rooms",
            params={"supplier_name": "测试酒店"}
        )
        assert supplier_filter.json()["count"] == 1
        wrong_supplier_filter = client.get(
            "/resources/hotel-rooms",
            params={"supplier_name": "其他供应商"}
        )
        assert wrong_supplier_filter.json()["count"] == 0

        inactive_filter = client.get(
            "/resources/attraction-tickets",
            params={"status": "inactive"}
        )
        assert inactive_filter.json()["count"] == 1
        active_filter = client.get(
            "/resources/attraction-tickets",
            params={"status": "active"}
        )
        assert active_filter.json()["count"] == 0

        max_cost_filter = client.get(
            "/resources/activities",
            params={"max_cost_price": 300}
        )
        assert max_cost_filter.json()["count"] == 1
        low_max_cost_filter = client.get(
            "/resources/activities",
            params={"max_cost_price": 299}
        )
        assert low_max_cost_filter.json()["count"] == 0

        available_filter = client.get(
            "/resources/transport",
            params={"available_on": "2026-07-01"}
        )
        assert available_filter.json()["count"] == 1
        calendar_priority_filter = client.get(
            "/resources/transport",
            params={"available_on": "2026-07-15"}
        )
        assert calendar_priority_filter.json()["count"] == 0
        unavailable_filter = client.get(
            "/resources/transport",
            params={"available_on": "2026-09-01"}
        )
        assert unavailable_filter.json()["count"] == 0

        range_fallback_filter = client.get(
            "/resources/hotel-rooms",
            params={"available_on": "2026-07-15"}
        )
        assert range_fallback_filter.json()["count"] == 1
        range_fallback_outside_filter = client.get(
            "/resources/hotel-rooms",
            params={"available_on": "2026-08-01"}
        )
        assert range_fallback_outside_filter.json()["count"] == 0

        has_stock_filter = client.get(
            "/resources/transport",
            params={"has_stock": True}
        )
        assert has_stock_filter.json()["count"] == 1
        no_stock_transport_filter = client.get(
            "/resources/transport",
            params={"has_stock": False}
        )
        assert no_stock_transport_filter.json()["count"] == 0
        no_stock_hotel_filter = client.get(
            "/resources/hotel-rooms",
            params={"has_stock": False}
        )
        assert no_stock_hotel_filter.json()["count"] == 1

        invalid_status_response = client.post(
            "/resources/attraction-tickets",
            json={**attraction_payload, "status": "archived"}
        )
        assert invalid_status_response.status_code == 422

        for inventory_field in (
            "stock_quantity",
            "sold_quantity",
            "reserved_quantity",
        ):
            negative_inventory_response = client.post(
                "/resources/transport",
                json={**transport_payload, inventory_field: -1}
            )
            assert negative_inventory_response.status_code == 422

        excessive_allocation_response = client.post(
            "/resources/transport",
            json={
                **transport_payload,
                "stock_quantity": 5,
                "sold_quantity": 3,
                "reserved_quantity": 3
            }
        )
        assert excessive_allocation_response.status_code == 422

        invalid_available_dates_response = client.post(
            "/resources/transport",
            json={**transport_payload, "available_dates": ["invalid-date"]}
        )
        assert invalid_available_dates_response.status_code == 422

        negative_cost_response = client.post(
            "/resources/restaurant-meals",
            json={**restaurant_payload, "cost_price": -1}
        )
        assert negative_cost_response.status_code == 422

        negative_sale_response = client.post(
            "/resources/activities",
            json={**activity_payload, "sale_price": -1}
        )
        assert negative_sale_response.status_code == 422


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
