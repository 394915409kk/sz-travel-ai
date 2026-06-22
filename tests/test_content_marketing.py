from datetime import date

from fastapi.testclient import TestClient

from apps.backend.main import app


def test_generate_xiaohongshu_and_video_content(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "content.db"))
    with TestClient(app) as client:
        note = client.post("/content-marketing/generate", json={
            "destination": "富国岛", "product_theme": "亲子海岛游", "target_audience": "亲子家庭",
            "platform": "xiaohongshu", "content_type": "note",
        }).json()["campaign"]
        assert "富国岛" in note["title"]
        assert "人工核验" in note["body"]
        video = client.post("/content-marketing/generate", json={
            "destination": "塞班", "platform": "douyin", "content_type": "short_video_script",
        }).json()["campaign"]
        assert "镜头1" in video["body"]
        assert client.get("/content-marketing/calendar", params={"date_from": date.today().isoformat(), "date_to": date.today().isoformat()}).json()["count"] == 2
        updated = client.patch(f"/content-marketing/{note['id']}/status", json={"status": "published"}).json()["campaign"]
        assert updated["published_at"] is not None
        assert client.get(f"/content-marketing/{note['id']}").status_code == 200


def test_high_margin_topics_use_quote_data(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "content_topics.db"))
    with TestClient(app) as client:
        inquiry_id = client.post("/inquiries", json={"customer_name": "主题客户", "destination": "塞班", "budget": 5000, "message": "内容主题"}).json()["inquiry_id"]
        resource = client.post("/resources/activities", json={
            "destination": "塞班", "resource_name": "高毛利主题资源", "supplier_name": "供应商",
            "activity_type": "tour", "duration": "半天", "suitable_people": "成人",
            "cost_price": 100, "sale_price": 500, "stock_quantity": 20,
        }).json()["resource"]
        client.post("/quotes/generate", json={"inquiry_id": inquiry_id, "target_margin": 0.3, "resource_items": [{"resource_type": "activity", "resource_id": resource["id"], "quantity": 1}]})
        topics = client.get("/content-marketing/high-margin-topics").json()["topics"]
        assert topics[0]["destination"] == "塞班"
        assert topics[0]["estimated_margin"] >= 0.2
