from db import get_connection


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS travel_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        destination TEXT NOT NULL,
        days INTEGER NOT NULL,
        price INTEGER NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL DEFAULT 'active'
    )
    """)

    cursor.execute("SELECT COUNT(*) FROM travel_products")
    count = cursor.fetchone()[0]

    if count == 0:
        products = [
            (
                "深圳出发·北京双飞5日游",
                "北京",
                5,
                3999,
                "国内游",
                "游览故宫、天安门、长城、颐和园等经典景点。",
                "active"
            ),
            (
                "深圳出发·云南昆明大理丽江6日游",
                "云南",
                6,
                4599,
                "国内游",
                "涵盖昆明、大理、丽江热门旅游线路。",
                "active"
            ),
            (
                "深圳出发·日本大阪京都东京7日游",
                "日本",
                7,
                8999,
                "出境游",
                "体验大阪、京都、东京经典城市路线。",
                "active"
            ),
            (
                "深圳出发·泰国曼谷芭提雅6日游",
                "泰国",
                6,
                4999,
                "出境游",
                "适合家庭、员工福利、团队旅游。",
                "active"
            ),
            (
                "深圳周边·惠州巽寮湾2日游",
                "惠州",
                2,
                699,
                "周边游",
                "适合公司团建、周末短途出行。",
                "active"
            )
        ]

        cursor.executemany("""
        INSERT INTO travel_products
        (title, destination, days, price, category, description, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, products)

    conn.commit()
    conn.close()

    print("旅游产品数据库初始化完成")


if __name__ == "__main__":
    init_database()
