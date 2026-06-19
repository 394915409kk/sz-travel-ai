from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.backend.db import get_connection
from apps.backend.services.agent_team import create_agent_team_analysis

router = APIRouter()


class RecommendationRequest(BaseModel):
    destination: str | None = None
    people_count: int | None = None
    budget: int | None = None
    message: str | None = None


def build_recommendations(destination=None, budget=None, message=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    SELECT id, title, destination, days, price, category, description, status
    FROM travel_products
    WHERE status = 'active'
    """

    params = []

    if destination:
        sql += " AND destination LIKE ?"
        params.append(f"%{destination}%")

    if budget:
        sql += " AND price <= ?"
        params.append(budget)

    sql += " ORDER BY price ASC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    recommendations = []

    for row in rows:
        reason_parts = []

        if destination and destination in row["destination"]:
            reason_parts.append(f"目的地匹配：{row['destination']}")

        if budget and row["price"] <= budget:
            reason_parts.append(f"价格 {row['price']} 元在预算 {budget} 元以内")

        if message and row["destination"] in message:
            reason_parts.append("客户咨询内容中提到了该目的地")

        if not reason_parts:
            reason_parts.append("根据当前客户需求推荐")

        recommendations.append({
            "id": row["id"],
            "title": row["title"],
            "destination": row["destination"],
            "days": row["days"],
            "price": row["price"],
            "category": row["category"],
            "description": row["description"],
            "reason": "；".join(reason_parts)
        })

    return recommendations


def get_active_product(product_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, title, destination, days, price, category, description, status
    FROM travel_products
    WHERE id = ? AND status = 'active'
    """, (product_id,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "id": row["id"],
        "title": row["title"],
        "destination": row["destination"],
        "days": row["days"],
        "price": row["price"],
        "category": row["category"],
        "description": row["description"],
        "status": row["status"]
    }


@router.post("/recommendations")
def recommend_products(request: RecommendationRequest):
    recommendations = build_recommendations(
        destination=request.destination,
        budget=request.budget,
        message=request.message
    )

    return {
        "success": True,
        "count": len(recommendations),
        "recommendations": recommendations
    }


@router.get("/inquiries/{inquiry_id}/recommendations")
def recommend_products_by_inquiry(inquiry_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, customer_name, phone, destination, people_count, budget,
           departure_date, message, follow_status, created_at
    FROM inquiries
    WHERE id = ?
    """, (inquiry_id,))

    inquiry = cursor.fetchone()
    conn.close()

    if inquiry is None:
        raise HTTPException(status_code=404, detail="未找到该客户咨询记录")

    recommendations = build_recommendations(
        destination=inquiry["destination"],
        budget=inquiry["budget"],
        message=inquiry["message"]
    )

    return {
        "success": True,
        "inquiry": {
            "id": inquiry["id"],
            "customer_name": inquiry["customer_name"],
            "phone": inquiry["phone"],
            "destination": inquiry["destination"],
            "people_count": inquiry["people_count"],
            "budget": inquiry["budget"],
            "departure_date": inquiry["departure_date"],
            "message": inquiry["message"],
            "follow_status": inquiry["follow_status"],
            "created_at": inquiry["created_at"]
        },
        "count": len(recommendations),
        "recommendations": recommendations
    }


@router.post("/products/{product_id}/ai-collaborative-strategy")
async def get_ai_collaborative_strategy(product_id: int):
    """
    基于真实产品数据生成多智能体协同营销策略。
    """
    product_data = get_active_product(product_id)

    if product_data is None:
        raise HTTPException(status_code=404, detail="未找到该旅游产品")

    try:
        return await create_agent_team_analysis(product_id, product_data)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"AI协同策略生成失败: {str(exc)}"
        ) from exc
