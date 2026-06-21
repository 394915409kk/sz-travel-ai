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


def init_follow_up_tasks_table(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS follow_up_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inquiry_id INTEGER NOT NULL,
        assigned_sales TEXT NOT NULL DEFAULT '未分配',
        task_title TEXT NOT NULL,
        task_status TEXT NOT NULL DEFAULT 'pending'
            CHECK (task_status IN ('pending', 'done', 'cancelled')),
        priority TEXT NOT NULL DEFAULT 'medium'
            CHECK (priority IN ('high', 'medium', 'low')),
        due_at TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (inquiry_id) REFERENCES inquiries(id)
    )
    """)

    cursor.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_follow_up_tasks_active_inquiry
    ON follow_up_tasks (inquiry_id)
    WHERE task_status IN ('pending', 'done')
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_follow_up_tasks_sales_status_due
    ON follow_up_tasks (assigned_sales, task_status, due_at)
    """)


def init_travel_resource_tables(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS travel_transport_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        destination TEXT NOT NULL,
        resource_name TEXT NOT NULL,
        supplier_name TEXT NOT NULL,
        transport_type TEXT NOT NULL,
        departure_city TEXT NOT NULL,
        arrival_city TEXT NOT NULL,
        cost_price REAL NOT NULL CHECK (cost_price >= 0),
        sale_price REAL NOT NULL CHECK (sale_price >= 0),
        stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
        sold_quantity INTEGER NOT NULL DEFAULT 0 CHECK (sold_quantity >= 0),
        reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
        currency TEXT NOT NULL DEFAULT 'CNY',
        available_start_date TEXT,
        available_end_date TEXT,
        available_dates TEXT,
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'inactive')),
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        CHECK (sold_quantity + reserved_quantity <= stock_quantity),
        CHECK (
            available_start_date IS NULL
            OR available_end_date IS NULL
            OR available_start_date <= available_end_date
        )
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hotel_room_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        destination TEXT NOT NULL,
        resource_name TEXT NOT NULL,
        supplier_name TEXT NOT NULL,
        hotel_name TEXT NOT NULL,
        room_type TEXT NOT NULL,
        breakfast_included INTEGER NOT NULL DEFAULT 0
            CHECK (breakfast_included IN (0, 1)),
        max_occupancy INTEGER NOT NULL CHECK (max_occupancy > 0),
        cost_price REAL NOT NULL CHECK (cost_price >= 0),
        sale_price REAL NOT NULL CHECK (sale_price >= 0),
        stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
        sold_quantity INTEGER NOT NULL DEFAULT 0 CHECK (sold_quantity >= 0),
        reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
        currency TEXT NOT NULL DEFAULT 'CNY',
        available_start_date TEXT,
        available_end_date TEXT,
        available_dates TEXT,
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'inactive')),
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        CHECK (sold_quantity + reserved_quantity <= stock_quantity),
        CHECK (
            available_start_date IS NULL
            OR available_end_date IS NULL
            OR available_start_date <= available_end_date
        )
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attraction_ticket_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        destination TEXT NOT NULL,
        resource_name TEXT NOT NULL,
        supplier_name TEXT NOT NULL,
        cost_price REAL NOT NULL CHECK (cost_price >= 0),
        sale_price REAL NOT NULL CHECK (sale_price >= 0),
        stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
        sold_quantity INTEGER NOT NULL DEFAULT 0 CHECK (sold_quantity >= 0),
        reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
        currency TEXT NOT NULL DEFAULT 'CNY',
        available_start_date TEXT,
        available_end_date TEXT,
        available_dates TEXT,
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'inactive')),
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        CHECK (sold_quantity + reserved_quantity <= stock_quantity),
        CHECK (
            available_start_date IS NULL
            OR available_end_date IS NULL
            OR available_start_date <= available_end_date
        )
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS restaurant_meal_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        destination TEXT NOT NULL,
        resource_name TEXT NOT NULL,
        supplier_name TEXT NOT NULL,
        meal_type TEXT NOT NULL,
        price_per_person REAL NOT NULL CHECK (price_per_person >= 0),
        cost_price REAL NOT NULL CHECK (cost_price >= 0),
        sale_price REAL NOT NULL CHECK (sale_price >= 0),
        stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
        sold_quantity INTEGER NOT NULL DEFAULT 0 CHECK (sold_quantity >= 0),
        reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
        currency TEXT NOT NULL DEFAULT 'CNY',
        available_start_date TEXT,
        available_end_date TEXT,
        available_dates TEXT,
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'inactive')),
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        CHECK (sold_quantity + reserved_quantity <= stock_quantity),
        CHECK (
            available_start_date IS NULL
            OR available_end_date IS NULL
            OR available_start_date <= available_end_date
        )
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        destination TEXT NOT NULL,
        resource_name TEXT NOT NULL,
        supplier_name TEXT NOT NULL,
        activity_type TEXT NOT NULL,
        duration TEXT NOT NULL,
        suitable_people TEXT NOT NULL,
        cost_price REAL NOT NULL CHECK (cost_price >= 0),
        sale_price REAL NOT NULL CHECK (sale_price >= 0),
        stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
        sold_quantity INTEGER NOT NULL DEFAULT 0 CHECK (sold_quantity >= 0),
        reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
        currency TEXT NOT NULL DEFAULT 'CNY',
        available_start_date TEXT,
        available_end_date TEXT,
        available_dates TEXT,
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'inactive')),
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        CHECK (sold_quantity + reserved_quantity <= stock_quantity),
        CHECK (
            available_start_date IS NULL
            OR available_end_date IS NULL
            OR available_start_date <= available_end_date
        )
    )
    """)

    resource_tables = (
        "travel_transport_resources",
        "hotel_room_resources",
        "attraction_ticket_resources",
        "restaurant_meal_resources",
        "activity_resources",
    )
    inventory_columns = {
        "stock_quantity": (
            "INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0)"
        ),
        "sold_quantity": (
            "INTEGER NOT NULL DEFAULT 0 CHECK (sold_quantity >= 0)"
        ),
        "reserved_quantity": (
            "INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0)"
        ),
        "available_dates": "TEXT",
    }

    for table_name in resource_tables:
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row["name"] for row in cursor.fetchall()}
        for column_name, column_definition in inventory_columns.items():
            if column_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE {table_name} "
                    f"ADD COLUMN {column_name} {column_definition}"
                )

        cursor.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{table_name}_filters
        ON {table_name} (destination, status, supplier_name, cost_price)
        """)


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    init_products_table(cursor)
    init_inquiries_table(cursor)
    init_follow_up_tasks_table(cursor)
    init_travel_resource_tables(cursor)

    conn.commit()
    conn.close()

    print("旅游产品、客户咨询、销售任务和旅游资源数据库初始化完成")


if __name__ == "__main__":
    init_database()
