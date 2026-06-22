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


def init_order_tables(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT NOT NULL UNIQUE,
        inquiry_id INTEGER,
        customer_name TEXT NOT NULL,
        phone TEXT,
        destination TEXT NOT NULL,
        people_count INTEGER NOT NULL DEFAULT 1 CHECK (people_count > 0),
        total_amount REAL NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
        paid_amount REAL NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),
        order_status TEXT NOT NULL DEFAULT 'draft'
            CHECK (
                order_status IN (
                    'draft', 'pending_payment', 'paid', 'fulfilling',
                    'completed', 'cancelled'
                )
            ),
        payment_status TEXT NOT NULL DEFAULT 'unpaid'
            CHECK (payment_status IN ('unpaid', 'mock_paid', 'refunded')),
        fulfillment_status TEXT NOT NULL DEFAULT 'pending'
            CHECK (
                fulfillment_status IN (
                    'pending', 'documents_pending', 'contract_pending',
                    'ready_to_travel', 'in_progress', 'completed'
                )
            ),
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (inquiry_id) REFERENCES inquiries(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        resource_type TEXT NOT NULL
            CHECK (
                resource_type IN (
                    'transport', 'hotel_room', 'attraction_ticket',
                    'restaurant_meal', 'activity'
                )
            ),
        resource_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_price REAL NOT NULL CHECK (unit_price >= 0),
        total_price REAL NOT NULL CHECK (total_price >= 0),
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        document_type TEXT NOT NULL,
        document_number TEXT NOT NULL,
        file_name TEXT,
        file_url TEXT,
        ocr_status TEXT NOT NULL DEFAULT 'pending'
            CHECK (ocr_status = 'pending'),
        ocr_raw_text TEXT,
        verified_status TEXT NOT NULL DEFAULT 'pending'
            CHECK (verified_status IN ('pending', 'verified', 'rejected')),
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS insurance_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        provider TEXT NOT NULL,
        coverage_summary TEXT,
        price REAL NOT NULL CHECK (price >= 0),
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'inactive'))
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_insurances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        insurance_product_id INTEGER NOT NULL,
        insured_customer_name TEXT NOT NULL,
        price REAL NOT NULL CHECK (price >= 0),
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (insurance_product_id) REFERENCES insurance_products(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_contracts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        contract_no TEXT NOT NULL UNIQUE,
        contract_status TEXT NOT NULL DEFAULT 'generated'
            CHECK (contract_status IN ('generated', 'signed')),
        contract_content TEXT NOT NULL,
        signed_at TEXT,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        reminder_type TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        remind_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'completed', 'cancelled')),
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_event_id TEXT NOT NULL UNIQUE,
        order_id INTEGER NOT NULL,
        event_status TEXT NOT NULL DEFAULT 'processing'
            CHECK (event_status IN ('processing', 'processed')),
        response_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        processed_at TEXT,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_orders_status
    ON orders (order_status, payment_status, fulfillment_status, created_at)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_order_items_order
    ON order_items (order_id)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_order_documents_order
    ON order_documents (order_id)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_order_insurances_order
    ON order_insurances (order_id)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_order_contracts_order
    ON order_contracts (order_id)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_order_reminders_order_status
    ON order_reminders (order_id, status, remind_at)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_payment_events_order
    ON payment_events (order_id, event_status)
    """)


def init_quote_tables(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_no TEXT NOT NULL UNIQUE,
        inquiry_id INTEGER,
        customer_name TEXT NOT NULL,
        phone TEXT,
        destination TEXT NOT NULL,
        people_count INTEGER NOT NULL DEFAULT 1 CHECK (people_count > 0),
        customer_budget REAL CHECK (customer_budget IS NULL OR customer_budget >= 0),
        target_margin REAL NOT NULL CHECK (target_margin >= 0 AND target_margin < 1),
        base_cost REAL NOT NULL DEFAULT 0 CHECK (base_cost >= 0),
        base_price REAL NOT NULL DEFAULT 0 CHECK (base_price >= 0),
        dynamic_adjustment REAL NOT NULL DEFAULT 0,
        final_price REAL NOT NULL DEFAULT 0 CHECK (final_price >= 0),
        estimated_profit REAL NOT NULL DEFAULT 0,
        estimated_margin REAL NOT NULL DEFAULT 0,
        quote_status TEXT NOT NULL DEFAULT 'draft'
            CHECK (
                quote_status IN (
                    'draft', 'proposed', 'accepted', 'rejected',
                    'expired', 'converted_to_order'
                )
            ),
        pricing_strategy TEXT NOT NULL DEFAULT 'mixed'
            CHECK (
                pricing_strategy IN (
                    'cost_plus', 'budget_based', 'inventory_based',
                    'margin_protection', 'mixed'
                )
            ),
        risk_flags TEXT NOT NULL DEFAULT '[]',
        recommendation TEXT,
        departure_date TEXT,
        converted_order_id INTEGER UNIQUE,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (inquiry_id) REFERENCES inquiries(id),
        FOREIGN KEY (converted_order_id) REFERENCES orders(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quote_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_id INTEGER NOT NULL,
        resource_type TEXT NOT NULL
            CHECK (
                resource_type IN (
                    'transport', 'hotel_room', 'attraction_ticket',
                    'restaurant_meal', 'activity'
                )
            ),
        resource_id INTEGER NOT NULL,
        resource_name TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_cost REAL NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
        unit_price REAL NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
        total_cost REAL NOT NULL DEFAULT 0 CHECK (total_cost >= 0),
        total_price REAL NOT NULL DEFAULT 0 CHECK (total_price >= 0),
        margin REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (quote_id) REFERENCES quotes(id)
    )
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_quotes_filters
    ON quotes (destination, quote_status, inquiry_id, created_at)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_quotes_margin_price
    ON quotes (estimated_margin, final_price)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_quote_items_quote
    ON quote_items (quote_id, id)
    """)


def init_sales_conversion_tables(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales_conversion_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inquiry_id INTEGER,
        quote_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        phone TEXT,
        destination TEXT NOT NULL,
        budget REAL CHECK (budget IS NULL OR budget >= 0),
        final_price REAL NOT NULL CHECK (final_price >= 0),
        conversion_probability REAL NOT NULL
            CHECK (conversion_probability >= 0 AND conversion_probability <= 1),
        conversion_stage TEXT NOT NULL DEFAULT 'new'
            CHECK (
                conversion_stage IN (
                    'new', 'quoted', 'negotiating', 'high_intent',
                    'low_intent', 'accepted', 'lost', 'converted'
                )
            ),
        customer_objections_json TEXT NOT NULL DEFAULT '[]',
        recommended_actions_json TEXT NOT NULL DEFAULT '[]',
        follow_up_script TEXT NOT NULL,
        risk_flags_json TEXT NOT NULL DEFAULT '[]',
        next_best_action TEXT NOT NULL,
        assigned_sales TEXT NOT NULL DEFAULT '未分配',
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (inquiry_id) REFERENCES inquiries(id),
        FOREIGN KEY (quote_id) REFERENCES quotes(id)
    )
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_sales_conversion_priority
    ON sales_conversion_records (
        conversion_stage, conversion_probability, updated_at
    )
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_sales_conversion_quote
    ON sales_conversion_records (quote_id, inquiry_id)
    """)


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    init_products_table(cursor)
    init_inquiries_table(cursor)
    init_follow_up_tasks_table(cursor)
    init_travel_resource_tables(cursor)
    init_order_tables(cursor)
    init_quote_tables(cursor)
    init_sales_conversion_tables(cursor)

    conn.commit()
    conn.close()

    print("旅游产品、咨询、任务、资源、订单和报价数据库初始化完成")


if __name__ == "__main__":
    init_database()
