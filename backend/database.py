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
            # Tạo dữ liệu với 2 Hợp đồng lớn, mỗi hợp đồng có 3 sản phẩm (dòng)
            orders = [
                # --- Hợp đồng 1: HD-2026-001 (3 sản phẩm) ---
                ("Công ty Cáp Quang Việt Nam", "HD-2026-001", "2026-06-25", "Trần A", "Nguyễn A", "OL-D2.5-08", "2026-06-25", "08:00", "12:00", "worker1", "Xanh dương", 8, 2.5, 2000.0, "Ghi chú 1", "Chưa xử lý"),
                ("Công ty Cáp Quang Việt Nam", "HD-2026-001", "2026-06-25", "Trần A", "Nguyễn A", "OL-D2.5-12", "2026-06-25", "13:00", "17:00", "worker1", "Cam", 12, 2.5, 2000.0, "Ghi chú 2", "Chưa xử lý"),
                ("Công ty Cáp Quang Việt Nam", "HD-2026-001", "2026-06-25", "Trần A", "Nguyễn A", "OL-D2.5-24", "2026-06-26", "08:00", "12:00", "worker1", "Xanh lá", 24, 2.5, 2000.0, "Ghi chú 3", "Chưa xử lý"),
                
                # --- Hợp đồng 2: HD-2026-002 (2 sản phẩm) ---
                ("Tập đoàn Viễn thông Á Châu", "HD-2026-002", "2026-06-25", "Trần A", "Quản đốc B", "OL-D3.0-24", "2026-06-27", "09:00", "15:00", "worker2", "Màu vàng", 24, 3.0, 1500.0, "Cần đóng gói kỹ", "Chưa xử lý"),
                ("Tập đoàn Viễn thông Á Châu", "HD-2026-002", "2026-06-25", "Trần A", "Quản đốc B", "OL-D3.0-48", "2026-06-27", "15:30", "18:00", "worker2", "Màu tím", 48, 3.0, 1500.0, "Hàng gấp", "Chưa xử lý")
            ]

            cursor.executemany("""
                INSERT INTO loose_tube_orders(
                    customer_name, contract_code, import_date, requester, approver, 
                    loose_tube_code, operation_date, start_time, end_time, operator, 
                    tube_color, fiber_count, diameter, length, notes, status
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, orders)

        conn.commit()
        conn.close()

    # ================= USERS =================

    def get_user(self, username):

        conn = self.get_connection()

        cursor = conn.cursor()

        cursor.execute("""

            SELECT *

            FROM users

            WHERE username=?

        """,(username,))

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
            cursor.execute("""
                SELECT *
                FROM loose_tube_orders
                ORDER BY
                    CASE status
                        WHEN 'Chưa xử lý' THEN 1
                        WHEN 'Đang xử lý' THEN 2
                        WHEN 'Hoàn thành' THEN 3
                        ELSE 4
                    END,
                    contract_code,
                    id
            """)

        elif username == "worker1":
            cursor.execute("""
                SELECT *
                FROM loose_tube_orders
                WHERE operator=?
                AND status='Chưa xử lý'
                ORDER BY contract_code,id
            """,(username,))

        else:
            conn.close()
            return []

        rows=[dict(r) for r in cursor.fetchall()]
        conn.close()

        result=[]
        groups={}

        for row in rows:

            code=row["contract_code"]

            if code not in groups:

                groups[code]={
                    "contract_code":row["contract_code"],
                    "customer_name":row["customer_name"],
                    "requester":row["requester"],
                    "approver":row["approver"],
                    "operator":row["operator"],
                    "import_date":row["import_date"],
                    "status":row["status"],
                    "product_count":0,
                    "details":[]
                }

                result.append(groups[code])

            groups[code]["details"].append(row)
            groups[code]["product_count"]+=1

        return result

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

    def update_order_status(self, contract_code, status):

        conn=self.get_connection()
        cursor=conn.cursor()

        cursor.execute("""
            UPDATE loose_tube_orders
            SET status=?
            WHERE contract_code=?
        """,(status,contract_code))

        conn.commit()
        conn.close()

    def get_contract(self, contract_code):

        conn=self.get_connection()
        cursor=conn.cursor()

        cursor.execute("""
            SELECT operator
            FROM loose_tube_orders
            WHERE contract_code=?
            LIMIT 1
        """,(contract_code,))

        row=cursor.fetchone()

        conn.close()

        return row
    
    def change_password(self, username, password_hash):

        conn = self.get_connection()

        cursor = conn.cursor()

        cursor.execute("""

            UPDATE users

            SET password_hash=?

            WHERE username=?

        """,(password_hash, username))

        conn.commit()

        conn.close()

db = Database()