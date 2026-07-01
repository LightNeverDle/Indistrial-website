
import pymysql
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Database:

    def __init__(self):
        self.init_db()

    def get_connection(self):
        return pymysql.connect(
            host="localhost",
            user="root",
            password="",
            database="factory_db",
            cursorclass=pymysql.cursors.DictCursor
        )

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # USERS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                username VARCHAR(50) PRIMARY KEY,
                password_hash TEXT,
                role VARCHAR(50)
            )
        """)

        cursor.execute("SELECT COUNT(*) as count FROM users")
        if cursor.fetchone()["count"] == 0:
            users = [
                ("admin", pwd_context.hash("123456"), "admin"),
                ("worker1", pwd_context.hash("123456"), "worker1"),
                ("worker2", pwd_context.hash("123456"), "worker2"),
            ]

            cursor.executemany(
                "INSERT INTO users VALUES(%s,%s,%s)",
                users
            )

        # ORDERS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loose_tube_orders(
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_name VARCHAR(255),
                contract_code VARCHAR(100),
                import_date DATE,
                requester VARCHAR(100),
                approver VARCHAR(100),
                loose_tube_code VARCHAR(100),
                operation_date DATE,
                start_time TIME,
                end_time TIME,
                operator VARCHAR(50),
                tube_color VARCHAR(50),
                fiber_count INT,
                diameter FLOAT,
                length FLOAT,
                notes TEXT,
                status VARCHAR(50)
            )
        """)

        cursor.execute("SELECT COUNT(*) as count FROM loose_tube_orders")
        if cursor.fetchone()["count"] == 0:
            orders = [
                ("Công ty Cáp Quang Việt Nam", "HD-2026-001", "2026-06-25", "Trần A", "Nguyễn A", "OL-D2.5-08", "2026-06-25", "08:00:00", "12:00:00", "worker1", "Xanh dương", 8, 2.5, 2000.0, "Ghi chú 1", "Chưa xử lý"),
                ("Công ty Cáp Quang Việt Nam", "HD-2026-001", "2026-06-25", "Trần A", "Nguyễn A", "OL-D2.5-12", "2026-06-25", "13:00:00", "17:00:00", "worker1", "Cam", 12, 2.5, 2000.0, "Ghi chú 2", "Chưa xử lý"),
                ("Công ty Cáp Quang Việt Nam", "HD-2026-001", "2026-06-25", "Trần A", "Nguyễn A", "OL-D2.5-24", "2026-06-26", "08:00:00", "12:00:00", "worker1", "Xanh lá", 24, 2.5, 2000.0, "Ghi chú 3", "Chưa xử lý"),
                ("Tập đoàn Viễn thông Á Châu", "HD-2026-002", "2026-06-25", "Trần A", "Quản đốc B", "OL-D3.0-24", "2026-06-27", "09:00:00", "15:00:00", "worker2", "Màu vàng", 24, 3.0, 1500.0, "Cần đóng gói kỹ", "Chưa xử lý"),
                ("Tập đoàn Viễn thông Á Châu", "HD-2026-002", "2026-06-25", "Trần A", "Quản đốc B", "OL-D3.0-48", "2026-06-27", "15:30:00", "18:00:00", "worker2", "Màu tím", 48, 3.0, 1500.0, "Hàng gấp", "Chưa xử lý")
            ]

            cursor.executemany("""
                INSERT INTO loose_tube_orders(
                    customer_name, contract_code, import_date, requester, approver,
                    loose_tube_code, operation_date, start_time, end_time, operator,
                    tube_color, fiber_count, diameter, length, notes, status
                ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, orders)

        conn.commit()
        conn.close()

    def get_user(self, username):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE username=%s
        """, (username,))

        user = cursor.fetchone()
        conn.close()
        return user

    def get_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT username, role FROM users")
        users = cursor.fetchall()

        conn.close()
        return users

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
                WHERE operator=%s
                AND status='Chưa xử lý'
                ORDER BY contract_code, id
            """, (username,))

        else:
            conn.close()
            return []

        rows = cursor.fetchall()
        conn.close()

        result = []
        groups = {}

        for row in rows:
            code = row["contract_code"]

            if code not in groups:
                groups[code] = {
                    "contract_code": row["contract_code"],
                    "customer_name": row["customer_name"],
                    "requester": row["requester"],
                    "approver": row["approver"],
                    "operator": row["operator"],
                    "import_date": str(row["import_date"]),
                    "status": row["status"],
                    "product_count": 0,
                    "details": []
                }
                result.append(groups[code])

            row["import_date"] = str(row["import_date"])
            row["operation_date"] = str(row["operation_date"])

            groups[code]["details"].append(row)
            groups[code]["product_count"] += 1

        return result

    def update_order_status(self, contract_code, status):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE loose_tube_orders
            SET status=%s
            WHERE contract_code=%s
        """, (status, contract_code))

        conn.commit()
        conn.close()

    def get_contract(self, contract_code):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT operator
            FROM loose_tube_orders
            WHERE contract_code=%s
            LIMIT 1
        """, (contract_code,))

        row = cursor.fetchone()
        conn.close()
        return row

    def change_password(self, username, password_hash):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users
            SET password_hash=%s
            WHERE username=%s
        """, (password_hash, username))

        conn.commit()
        conn.close()


db = Database()

