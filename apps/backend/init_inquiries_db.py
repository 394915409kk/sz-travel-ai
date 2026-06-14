from apps.backend.init_db import init_database


def init_inquiries_table():
    init_database()
    print("客户咨询记录数据库表初始化完成")


if __name__ == "__main__":
    init_inquiries_table()
