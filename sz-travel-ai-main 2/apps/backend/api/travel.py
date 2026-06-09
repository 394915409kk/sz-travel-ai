from fastapi import APIRouter, Query
from apps.backend.db import get_connection

router = APIRouter()


@router.get("/products")
def get_products(
    destination: str | None = Query(default=None, description="目的地"),
    category: str | None = Query(default=None, description="产品类型"),
    max_price: int | None = Query(default=None, description="最高价格")
):
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

    if category:
        sql += " AND category = ?"
        params.append(category)

    if max_price:
        sql += " AND price <= ?"
        params.append(max_price)

    sql += " ORDER BY id DESC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    products = []

    for row in rows:
        products.append({
            "id": row["id"],
            "title": row["title"],
            "destination": row["destination"],
            "days": row["days"],
            "price": row["price"],
            "category": row["category"],
            "description": row["description"],
            "status": row["status"]
        })

    return {
        "success": True,
        "count": len(products),
        "products": products
    }


@router.get("/products/{product_id}")
def get_product_detail(product_id: int):
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
        return {
            "success": False,
            "message": "未找到该旅游产品"
        }

    return {
        "success": True,
        "product": {
            "id": row["id"],
            "title": row["title"],
            "destination": row["destination"],
            "days": row["days"],
            "price": row["price"],
            "category": row["category"],
            "description": row["description"],
            "status": row["status"]
        }
    }
