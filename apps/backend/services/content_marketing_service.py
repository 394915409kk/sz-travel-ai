import json
from collections import defaultdict
from datetime import date, datetime

from fastapi import HTTPException

from apps.backend.db import get_connection
from apps.backend.services.inventory_service import RESOURCE_TABLES
from apps.backend.services.profit_service import ProfitService


def serialize_campaign(row):
    campaign = dict(row)
    for source, target in (("hashtags_json", "hashtags"), ("related_resource_ids_json", "related_resource_ids")):
        try:
            value = json.loads(campaign.pop(source) or "[]")
            campaign[target] = value if isinstance(value, list) else []
        except json.JSONDecodeError:
            campaign[target] = []
    return campaign


class ContentMarketingService:
    """使用本地经营数据和固定模板生成待人工审核的内容任务。"""

    @classmethod
    def generate(cls, payload):
        conn = get_connection()
        cursor = conn.cursor()
        destination = payload["destination"]
        metrics = cls._destination_metrics(conn, destination)
        theme = payload.get("product_theme") or f"{destination}旅行灵感"
        audience = payload.get("target_audience") or "计划出行客户"
        platform = payload["platform"]
        content_type = payload["content_type"]
        title, body, hashtags, cta = cls._render(
            destination, theme, audience, platform, content_type
        )
        priority = cls._priority(metrics)
        campaign_name = payload.get("campaign_name") or f"{destination}-{platform}-{content_type}"
        resource_ids = payload.get("related_resource_ids") or []

        cursor.execute(
            """
            INSERT INTO content_campaigns (
                campaign_name, destination, product_theme, target_audience,
                platform, content_type, title, body, hashtags_json,
                call_to_action, related_product_id, related_resource_ids_json,
                estimated_margin, priority_score, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
            """,
            (
                campaign_name, destination, theme, audience, platform,
                content_type, title, body,
                json.dumps(hashtags, ensure_ascii=False), cta,
                payload.get("related_product_id"),
                json.dumps(resource_ids, ensure_ascii=False),
                metrics["estimated_margin"], priority,
            ),
        )
        campaign_id = cursor.lastrowid
        conn.commit()
        row = cls._get(cursor, campaign_id)
        conn.close()
        return serialize_campaign(row)

    @staticmethod
    def _render(destination, theme, audience, platform, content_type):
        hashtags = [destination, "旅行攻略", "深圳出发"]
        cta = "评论或咨询获取经人工核价的行程方案"
        if platform == "xiaohongshu" or content_type == "note":
            title = f"{destination}怎么玩？这份{theme}清单先收藏"
            body = (
                f"适合{audience}的{destination}行程思路：先确认出发日期和人数，"
                "再按交通、住宿与体验组合预算。文案中的价格、库存和政策均需人工核验；"
                f"{cta}。"
            )
        elif content_type == "short_video_script" or platform in ("douyin", "video_account"):
            title = f"30秒看懂{destination}{theme}"
            body = (
                f"镜头1（3秒）：想去{destination}但不会选？\n"
                f"镜头2（12秒）：展示{theme}的交通、住宿、体验三类选择。\n"
                "镜头3（10秒）：提醒不同日期库存与价格会变化，以人工核验为准。\n"
                f"镜头4（5秒）：{cta}。"
            )
        elif content_type == "poster_copy":
            title = f"{destination}出发计划"
            body = f"{theme}\n适合：{audience}\n价格/库存/政策：待人工确认\n{cta}"
        elif content_type == "itinerary_post":
            title = f"{destination}行程设计参考"
            body = f"围绕{theme}规划每日节奏，先核对交通与住宿资源，再补充体验项目。{cta}。"
        else:
            title = f"{destination}{theme}活动预告"
            body = f"面向{audience}整理的{destination}方案，正式发布前需复核价格、库存与政策。{cta}。"
        return title, body, hashtags, cta

    @classmethod
    def _destination_metrics(cls, conn, destination):
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM inquiries WHERE destination = ?", (destination,))
        inquiry_count = cursor.fetchone()["count"]
        cursor.execute("SELECT AVG(estimated_margin) AS margin FROM quotes WHERE destination = ?", (destination,))
        quote_margin = cursor.fetchone()["margin"]
        cursor.execute(
            """
            SELECT COUNT(*) AS count FROM quotes
            WHERE destination = ? AND departure_date IS NOT NULL
              AND date(departure_date) BETWEEN date('now', 'localtime')
                                           AND date('now', 'localtime', '+30 days')
            """,
            (destination,),
        )
        departure_window_count = cursor.fetchone()["count"]
        order_profits = ProfitService(conn).list_order_profits(destination=destination)
        high_profit_count = sum(item["profit_level"] == "high_profit" for item in order_profits)
        ceo_risk_count = sum(bool(item["risk_flags"]) for item in order_profits if item["created_at"][:10] == date.today().isoformat())
        available = total = 0
        for table in RESOURCE_TABLES.values():
            cursor.execute(
                f"SELECT COALESCE(SUM(stock_quantity - sold_quantity - reserved_quantity), 0) AS available, COALESCE(SUM(stock_quantity), 0) AS total FROM {table} WHERE destination = ? AND status = 'active'",
                (destination,),
            )
            row = cursor.fetchone()
            available += row["available"]
            total += row["total"]
        return {
            "inquiry_count": inquiry_count,
            "estimated_margin": round(float(quote_margin or 0), 4),
            "stock_ratio": round(available / total, 4) if total > 0 else 0.0,
            "departure_window_count": departure_window_count,
            "high_profit_count": high_profit_count,
            "ceo_risk_count": ceo_risk_count,
        }

    @staticmethod
    def _priority(metrics):
        demand_score = min(metrics["inquiry_count"] * 4, 20)
        margin_score = min(max(metrics["estimated_margin"], 0) * 100, 35)
        stock_score = metrics["stock_ratio"] * 20
        departure_score = min(metrics.get("departure_window_count", 0) * 5, 10)
        high_profit_score = min(metrics.get("high_profit_count", 0) * 5, 10)
        ceo_risk_adjustment = -min(metrics.get("ceo_risk_count", 0) * 5, 10)
        completeness = 5 if metrics["estimated_margin"] > 0 else 0
        return round(max(0, min(100, demand_score + margin_score + stock_score + departure_score + high_profit_score + ceo_risk_adjustment + completeness)), 2)

    @classmethod
    def high_margin_topics(cls):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT destination FROM quotes UNION SELECT DISTINCT destination FROM orders")
        destinations = [row["destination"] for row in cursor.fetchall() if row["destination"]]
        topics = []
        profits = ProfitService(conn).list_order_profits()
        profit_groups = defaultdict(list)
        for profit in profits:
            profit_groups[profit["destination"]].append(profit)
        for destination in destinations:
            metrics = cls._destination_metrics(conn, destination)
            order_group = profit_groups[destination]
            revenue = sum(item["order_revenue"] for item in order_group)
            gross_profit = sum(item["gross_profit"] for item in order_group)
            order_margin = round(gross_profit / revenue, 4) if revenue > 0 else 0.0
            effective_margin = max(metrics["estimated_margin"], order_margin)
            if effective_margin >= 0.20:
                topics.append({
                    "destination": destination,
                    "estimated_margin": effective_margin,
                    "priority_score": cls._priority({**metrics, "estimated_margin": effective_margin}),
                    "reason": "历史报价或订单毛利率达到 20% 规则阈值",
                })
        conn.close()
        return sorted(topics, key=lambda item: (item["priority_score"], item["estimated_margin"]), reverse=True)

    @classmethod
    def list_campaigns(cls, status=None, platform=None, date_from=None, date_to=None):
        conn = get_connection()
        cursor = conn.cursor()
        sql = "SELECT * FROM content_campaigns"
        conditions = []
        params = []
        for column, value in (("status", status), ("platform", platform)):
            if value:
                conditions.append(f"{column} = ?")
                params.append(value)
        if date_from:
            conditions.append("date(created_at) >= date(?)")
            params.append(str(date_from))
        if date_to:
            conditions.append("date(created_at) <= date(?)")
            params.append(str(date_to))
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY priority_score DESC, id DESC"
        cursor.execute(sql, params)
        campaigns = [serialize_campaign(row) for row in cursor.fetchall()]
        conn.close()
        return campaigns

    @classmethod
    def get(cls, campaign_id):
        conn = get_connection()
        cursor = conn.cursor()
        row = cls._get(cursor, campaign_id)
        conn.close()
        if row is None:
            raise HTTPException(status_code=404, detail="未找到该内容营销任务")
        return serialize_campaign(row)

    @staticmethod
    def _get(cursor, campaign_id):
        cursor.execute("SELECT * FROM content_campaigns WHERE id = ?", (campaign_id,))
        return cursor.fetchone()

    @classmethod
    def update_status(cls, campaign_id, status):
        conn = get_connection()
        cursor = conn.cursor()
        existing = cls._get(cursor, campaign_id)
        if existing is None:
            conn.close()
            raise HTTPException(status_code=404, detail="未找到该内容营销任务")
        published_at = existing["published_at"]
        if status == "published" and not published_at:
            published_at = datetime.now().isoformat(timespec="seconds")
        cursor.execute(
            "UPDATE content_campaigns SET status = ?, published_at = ?, updated_at = ? WHERE id = ?",
            (status, published_at, datetime.now().isoformat(timespec="seconds"), campaign_id),
        )
        conn.commit()
        row = cls._get(cursor, campaign_id)
        conn.close()
        return serialize_campaign(row)
