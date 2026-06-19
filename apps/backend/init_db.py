from apps.backend.db import get_connection


PRODUCT_SEED_DATA = [
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


def init_products_table(cursor):
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
        cursor.executemany("""
        INSERT INTO travel_products
        (title, destination, days, price, category, description, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, PRODUCT_SEED_DATA)


def init_inquiries_table(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        phone TEXT,
        destination TEXT,
        people_count INTEGER,
        budget INTEGER,
        departure_date TEXT,
        message TEXT NOT NULL,
        follow_status TEXT NOT NULL DEFAULT 'new',
        source TEXT NOT NULL DEFAULT '未知',
        assigned_sales TEXT NOT NULL DEFAULT '未分配',
        priority TEXT NOT NULL DEFAULT 'medium',
        last_contact_at TEXT,
        next_follow_up_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    )
    """)

    cursor.execute("PRAGMA table_info(inquiries)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    extra_columns = {
        "source": "TEXT NOT NULL DEFAULT '未知'",
        "assigned_sales": "TEXT NOT NULL DEFAULT '未分配'",
        "priority": "TEXT NOT NULL DEFAULT 'medium'",
        "last_contact_at": "TEXT",
        "next_follow_up_at": "TEXT",
    }

    for column_name, column_definition in extra_columns.items():
        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE inquiries ADD COLUMN {column_name} {column_definition}"
            )


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    init_products_table(cursor)
    init_inquiries_table(cursor)

    conn.commit()
    conn.close()

    print("旅游产品和客户咨询数据库初始化完成")


if __name__ == "__main__":
    init_database()
