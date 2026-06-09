from db import get_connection


def init_inquiries_table():
    conn = get_connection()
    cursor = conn.cursor()

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
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    )
    """)

    conn.commit()
    conn.close()

    print("客户咨询记录数据库表初始化完成")


if __name__ == "__main__":
    init_inquiries_table()
