import os
import sqlite3
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DB_PATH = "backend/factory.db"


class Database:

    def __init__(self):
        os.makedirs("backend", exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # USERS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                username TEXT PRIMARY KEY,
                password_hash TEXT,
                role TEXT
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM users")

        if cursor.fetchone()[0] == 0:
            users = [
                ("admin", pwd_context.hash("123456"), "admin"),
                ("worker1", pwd_context.hash("123456"), "worker1"),
                ("worker2", pwd_context.hash("123456"), "worker2"),
            ]

            cursor.executemany(
                "INSERT INTO users VALUES(?,?,?)",
                users
            )

        # ORDERS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loose_tube_orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT,
                contract_code TEXT,
                import_date TEXT,
                requester TEXT,
                approver TEXT,
                loose_tube_code TEXT,
                operation_date TEXT,
                start_time TEXT,
                end_time TEXT,
                operator TEXT,
                tube_color TEXT,
                fiber_count INTEGER,
                diameter REAL,
                length REAL,
                notes TEXT,
                status TEXT
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM loose_tube_orders")

        if cursor.fetchone()[0] == 0:

            orders = [
                (
                    "Công ty Cáp Quang Việt Nam",
                    "HD-2026-001",
                    "2026-06-25",
                    "Trần Văn A",
                    "Quản đốc Nguyễn Văn A",
                    "OL-D2.5-08",
                    "2026-06-25",
                    "08:00",
                    "12:00",
                    "worker1",
                    "Xanh dương",
                    8,
                    2.5,
                    2000.0,
                    "Yêu cầu kiểm tra kỹ độ căng sợi",
                    "Chưa xử lý"
                ),
                (
                    "Tập đoàn Viễn thông Á Châu",
                    "HD-2026-002",
                    "2026-06-25",
                    "Trần Văn A",
                    "Quản đốc Nguyễn Văn A",
                    "OL-D3.0-24",
                    "2026-06-25",
                    "13:30",
                    "17:30",
                    "worker1",
                    "Màu vàng",
                    24,
                    3.0,
                    1500.0,
                    "Đóng gói bằng rulo gỗ bọc màng PE",
                    "Chưa xử lý"
                ),
                (
                    "Bưu điện Thành phố",
                    "HD-2026-003",
                    "2026-06-25",
                    "Trần Văn A",
                    "Trưởng ca Lê Văn B",
                    "OL-D2.0-04",
                    "2026-06-26",
                    "07:30",
                    "11:30",
                    "worker1",
                    "Màu đỏ",
                    4,
                    2.0,
                    3500.0,
                    "Giao hàng trước 4h chiều",
                    "Chưa xử lý"
                )
            ]

            cursor.executemany("""
                INSERT INTO loose_tube_orders(
                    customer_name,
                    contract_code,
                    import_date,
                    requester,
                    approver,
                    loose_tube_code,
                    operation_date,
                    start_time,
                    end_time,
                    operator,
                    tube_color,
                    fiber_count,
                    diameter,
                    length,
                    notes,
                    status
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, orders)

        conn.commit()
        conn.close()

    # ================= USERS =================

    def get_user(self, username):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT password_hash,role FROM users WHERE username=?",
            (username,)
        )

        user = cursor.fetchone()

        conn.close()

        return user

    def get_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT username,role FROM users")

        users = [
            {
                "username": row["username"],
                "role": row["role"]
            }
            for row in cursor.fetchall()
        ]

        conn.close()

        return users

    # ================= ORDERS =================

    def get_orders(self, role, username):

        conn = self.get_connection()
        cursor = conn.cursor()

        if role == "admin":
            cursor.execute("SELECT * FROM loose_tube_orders")

        elif username == "worker1":
            cursor.execute("""
                SELECT *
                FROM loose_tube_orders
                WHERE status='Chưa xử lý'
            """)

        else:
            cursor.execute("SELECT * FROM loose_tube_orders WHERE 1=0")

        orders = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return orders

    def get_order(self, order_id):

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT operator,status
            FROM loose_tube_orders
            WHERE id=?
        """, (order_id,))

        order = cursor.fetchone()

        conn.close()

        return order

    def update_order_status(self, order_id, status):

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE loose_tube_orders
            SET status=?
            WHERE id=?
        """, (status, order_id))

        conn.commit()
        conn.close()


db = Database()