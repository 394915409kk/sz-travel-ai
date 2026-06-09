from fastapi import APIRouter
from pydantic import BaseModel
from apps.backend.db import get_connection

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
        return {
            "success": False,
            "message": "未找到该客户咨询记录"
        }

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
# =====================================================================
# 一人公司超级个体总指挥部：多智能体协同（战略+定位+文案）全自动流水线接口
# =====================================================================
@router.post("/{product_id}/ai-collaborative-strategy")
async def get_ai_collaborative_strategy(product_id: int):
    """
    24小时全自动多智能体协同营销路由
    自动激活：AI战略专家、AI定位专家、AI文案大师，生成一键种草文案与营销矩阵
    """
    import json
    # 1. 模拟从本地数据库/或当前上下文检索产品数据（锁死 2-3月早鸟塞班 4999元起 核心线索）
    mock_product_data = {
        "title": "2-3月早鸟塞班·香港直飞马里亚纳机酒自由行套餐",
        "destination": "saipan",
        "price": "4999元起包含往返机票和酒店",
        "flight_number": "HX072/HX073"
    }
    
    try:
        # 2. 动态引入我们上一阶段手动固化好的 services/agent_team.py 三专家协同大脑
        from apps.backend.services.agent_team import create_agent_team_analysis
        
        # 3. 让战略、定位、文案三大总监在后台系统进行 Chain-of-Thought（思维链）群聊研讨
        analysis_result = await create_agent_team_analysis(product_id, mock_product_data)
        return analysis_result
        
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"AI超级个体协同流水线中断: {str(e)}")
