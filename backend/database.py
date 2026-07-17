# =====================================================================
# SMART FACTORY — DATABASE LAYER (MySQL)
# =====================================================================
# Đã chuyển hoàn toàn từ SQLite sang MySQL (PyMySQL driver).
# Bảng trung tâm: cable_rolls — khớp với factory_management.sql đã thống
# nhất trước đó (không còn dùng bảng loose_tube_orders phẳng nữa).
#
# Cấu hình kết nối lấy từ biến môi trường (xem .env.example):
#   DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
# =====================================================================

import os
import json
from datetime import datetime

import pymysql
import pymysql.cursors
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "factory_management")

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

# Bảng thông tin sản xuất tương ứng theo từng loại sản phẩm
PRODUCTION_TABLE_BY_TYPE = {
    "loose_tube": "production_info_loose_tube",
    "sz": "production_info_sz",
    "jacket": "production_info_jacket",
}

PLAN_TABLE_BY_TYPE = {
    "loose_tube": "plan_loose_tube",
    "sz": "plan_sz",
    "jacket": "plan_jacket",
}

# Vòng đời trạng thái của cable_rolls
NEXT_STATUS = {
    "pending": "processing",
    "processing": "pending-inspect",
    "rejected": "processing",
}


class Database:

    def __init__(self):
        self._ensure_database_exists()
        self.init_db()

    # -----------------------------------------------------------------
    # KẾT NỐI
    # -----------------------------------------------------------------
    def _ensure_database_exists(self):
        """Tạo database nếu chưa tồn tại (chạy 1 lần khi khởi động)."""
        conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
            charset="utf8mb4", autocommit=True
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
                )
        finally:
            conn.close()

    def get_connection(self):
        return pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )

    def init_db(self):
        """Tạo toàn bộ bảng theo schema.sql + seed dữ liệu mẫu nếu trống."""
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                for statement in schema_sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        cursor.execute(statement)
            conn.commit()

            with conn.cursor() as cursor:
                cursor.execute("SHOW COLUMNS FROM qc_reports LIKE 'shift'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE qc_reports ADD COLUMN shift VARCHAR(50) DEFAULT NULL")

                # Add inventory / checklist columns to cable_rolls if missing
                cursor.execute("SHOW COLUMNS FROM cable_rolls LIKE 'in_inventory'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE cable_rolls ADD COLUMN in_inventory TINYINT(1) DEFAULT 0")

                cursor.execute("SHOW COLUMNS FROM cable_rolls LIKE 'checklist_status'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE cable_rolls ADD COLUMN checklist_status VARCHAR(100) DEFAULT NULL")

                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'product_code'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN product_code VARCHAR(100) DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'machine'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN machine VARCHAR(100) DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'machine_speed'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN machine_speed FLOAT DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'sz_pitch'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN sz_pitch VARCHAR(100) DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'lay_direction'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN lay_direction VARCHAR(100) DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'tension'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN tension VARCHAR(100) DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'pull_speed'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN pull_speed FLOAT DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'post_braid_diameter'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN post_braid_diameter FLOAT DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'kcs_diameter'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN kcs_diameter FLOAT DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'kcs_uniformity'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN kcs_uniformity VARCHAR(100) DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'kcs_external_inspection'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN kcs_external_inspection VARCHAR(255) DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM sz_production_forms LIKE 'kcs_notes'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE sz_production_forms ADD COLUMN kcs_notes TEXT DEFAULT NULL")

                cursor.execute("SHOW COLUMNS FROM jacket_production_forms LIKE 'shift'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE jacket_production_forms ADD COLUMN shift VARCHAR(50) DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM jacket_production_forms LIKE 'bin'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE jacket_production_forms ADD COLUMN bin VARCHAR(100) DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM jacket_production_forms LIKE 'frp'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE jacket_production_forms ADD COLUMN frp VARCHAR(100) DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM jacket_production_forms LIKE 'kcs_measurements'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE jacket_production_forms ADD COLUMN kcs_measurements TEXT DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM jacket_production_forms LIKE 'measured_length'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE jacket_production_forms ADD COLUMN measured_length FLOAT DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM jacket_production_forms LIKE 'loss_result'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE jacket_production_forms ADD COLUMN loss_result VARCHAR(100) DEFAULT NULL")
                cursor.execute("SHOW COLUMNS FROM jacket_production_forms LIKE 'measured_by'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE jacket_production_forms ADD COLUMN measured_by VARCHAR(100) DEFAULT NULL")

                cursor.execute("SELECT COUNT(*) AS c FROM users")
                if cursor.fetchone()["c"] == 0:
                    self._seed_data(conn)
        finally:
            conn.close()

    def _seed_data(self, conn):
        with conn.cursor() as cursor:
            users = [
                ("admin", pwd_context.hash("123456"), "Administrator", "admin", "BA"),
                ("worker1", pwd_context.hash("123456"), "Công nhân 1", "worker1", "Sản xuất"),
                ("worker2", pwd_context.hash("123456"), "Công nhân 2", "worker2", "Sản xuất"),
                ("inspector", pwd_context.hash("123456"), "Kiểm định viên", "inspector", "QC"),
            ]
            cursor.executemany(
                "INSERT INTO users (username, password_hash, full_name, role, department) "
                "VALUES (%s, %s, %s, %s, %s)",
                users,
            )

            # Lấy id của user vừa tạo để gán operator/checked_by/updated_by
            cursor.execute("SELECT id, username FROM users")
            uid = {row["username"]: row["id"] for row in cursor.fetchall()}

            # ---------------- HỢP ĐỒNG ----------------
            cursor.execute(
                "INSERT INTO contracts (contract_code, customer_name, requester, approver, created_date, status) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                ("HD-2026-001", "Công ty Cáp Quang Việt Nam", "Trần A", "Nguyễn A", "2026-06-25", "processing"),
            )
            contract_1 = cursor.lastrowid

            cursor.execute(
                "INSERT INTO contracts (contract_code, customer_name, requester, approver, created_date, status) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                ("HD-2026-002", "Tập đoàn Viễn thông Á Châu", "Trần A", "Quản đốc B", "2026-06-27", "processing"),
            )
            contract_2 = cursor.lastrowid

            # Hợp đồng khớp 3 phiếu lệnh thực tế (Ống Lỏng 59.2025 + Lõi SZ dùng chung, Bọc Vỏ Cáp 58.2025)
            cursor.execute(
                "INSERT INTO contracts (contract_code, customer_name, requester, approver, created_date, status) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                ("59.2025", "Bộ Công An", None, "Vũ Việt Khanh", "2025-12-11", "processing"),
            )
            contract_3 = cursor.lastrowid

            cursor.execute(
                "INSERT INTO contracts (contract_code, customer_name, requester, approver, created_date, status) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                ("58.2025", "VTVCAP", None, "Vũ Việt Khanh", "2025-12-11", "processing"),
            )
            contract_4 = cursor.lastrowid

            # ---------------- LÔ SẢN PHẨM (cable_rolls) ----------------
            # Rải đều 4 trạng thái x 3 loại sản phẩm để demo đủ các tab trên frontend
            rolls = [
                # roll_code,     product_type,  length, stage,        status,            contract
                ("OL-D2.5-08",   "loose_tube",  2000.0, "Đùn ống",    "pending",         contract_1),
                ("BOC-002",      "jacket",      1500.0, "Bọc vỏ",     "pending",         contract_2),
                ("OL-D2.5-12",   "loose_tube",  2000.0, "Đùn ống",    "processing",      contract_1),
                ("SZ-001",       "sz",          1800.0, "Bện SZ",     "processing",      contract_2),
                ("OL-D2.5-24",   "loose_tube",  2000.0, "Đùn ống",    "pending-inspect", contract_1),
                ("BOC-001",      "jacket",      1500.0, "Bọc vỏ",     "pending-inspect", contract_2),
                ("SZ-002",       "sz",          1800.0, "Bện SZ",     "rejected",        contract_2),
                ("OL-D3.0-48",   "loose_tube",  1500.0, "Hoàn thành", "completed",       contract_1),
                # ---- 3 lệnh thực tế (khớp phiếu giấy đã chụp) ----
                ("OL-59-2025",   "loose_tube",  None,   "Đùn ống",    "pending-inspect", contract_3),
                ("SZ-59-2025",   "sz",          None,   "Bện SZ",     "pending-inspect", contract_3),
                ("BOC-58-2025",  "jacket",      None,   "Bọc vỏ",     "pending-inspect", contract_4),
            ]

            roll_id = {}
            for roll_code, product_type, length, stage, status, contract_id in rolls:
                cursor.execute(
                    "INSERT INTO cable_rolls (contract_id, roll_code, product_type, length, current_stage, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (contract_id, roll_code, product_type, length, stage, status),
                )
                roll_id[roll_code] = cursor.lastrowid

            now = datetime.now()

            def add_material_prep(roll_code, stage, prepared_by, items):
                cursor.execute(
                    "INSERT INTO material_preparations (roll_id, stage, prepared_by, prepared_date, status) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (roll_id[roll_code], stage, uid[prepared_by], now, "Hoàn thành"),
                )
                prep_id = cursor.lastrowid
                for item_name, quantity, unit, notes in items:
                    cursor.execute(
                        "INSERT INTO material_preparation_items (preparation_id, item_name, quantity, unit, notes) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (prep_id, item_name, quantity, unit, notes),
                    )

            def add_log(roll_code, stage, status, updated_by, notes=None):
                cursor.execute(
                    "INSERT INTO production_logs (roll_id, stage, status, updated_by, updated_at, notes) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (roll_id[roll_code], stage, status, uid[updated_by], now, notes),
                )

            # ---------------- OL-D2.5-08 (pending — chưa ai nhận) ----------------
            add_material_prep("OL-D2.5-08", "Chuẩn bị vật tư", "worker1", [
                ("Hạt nhựa PBT", 50, "kg", "Dùng cho ống đệm"),
                ("Sợi quang G652D", 8, "cuộn", None),
            ])

            # ---------------- BOC-002 (pending) ----------------
            add_material_prep("BOC-002", "Chuẩn bị vật tư", "worker2", [
                ("Hạt nhựa HDPE", 80, "kg", None),
                ("Băng giáp thép", 2, "cuộn", "Loại chống gặm nhấm"),
            ])

            # ---------------- OL-D2.5-12 (processing) ----------------
            add_material_prep("OL-D2.5-12", "Chuẩn bị vật tư", "worker1", [
                ("Hạt nhựa PBT", 45, "kg", None),
                ("Sợi quang G652D", 12, "cuộn", None),
            ])
            cursor.execute(
                "INSERT INTO plan_loose_tube (roll_id, operation_date, start_time, end_time, operator, "
                "tube_color, fiber_count, diameter, length, notes, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (roll_id["OL-D2.5-12"], "2026-07-06", "08:00:00", "12:00:00", "worker1",
                 "Cam", 12, 2.5, 2000.0, "Ghi chú kế hoạch", "Đang xử lý"),
            )
            cursor.execute(
                "INSERT INTO production_info_loose_tube (roll_id, stt, fiber_code, shift, tube_code, "
                "machine_speed, color, fiber_count, diameter, bobbin_count, operator, notes) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (roll_id["OL-D2.5-12"], 1, "FB-0012", "Ca sáng", "OL-D2.5-12",
                 850.5, "Cam", 12, 2.5, 12, uid["worker1"], "Đang chạy máy 01"),
            )
            add_log("OL-D2.5-12", "Đùn ống", "processing", "worker1", "Đã nhận việc và bắt đầu sản xuất")

            # ---------------- SZ-001 (processing) ----------------
            add_material_prep("SZ-001", "Chuẩn bị vật tư", "worker2", [
                ("Băng chặn nước", 5, "cuộn", None),
                ("Sợi binder", 10, "kg", None),
            ])
            cursor.execute(
                "INSERT INTO plan_sz (roll_id, operation_date, start_time, end_time, operator, core_color, "
                "cam, tube, water_blocking_tape, fpr, kcs, water_blocking_yarn, binder, notes, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (roll_id["SZ-001"], "2026-07-06", "09:00:00", "15:00:00", "worker2",
                 "Xanh dương", "Cam 1", "Ống 12FO", "Có", "FPR-01", "KCS-01", "Có", "BD-01",
                 "Bện theo đơn hàng gấp", "Đang xử lý"),
            )
            cursor.execute(
                "INSERT INTO production_info_sz (roll_id, operator, notes) VALUES (%s, %s, %s)",
                (roll_id["SZ-001"], uid["worker2"], "Đang bện SZ trên máy 02"),
            )
            add_log("SZ-001", "Bện SZ", "processing", "worker2", "Đã nhận việc")

            # ---------------- OL-D2.5-24 (pending-inspect) ----------------
            add_material_prep("OL-D2.5-24", "Chuẩn bị vật tư", "worker1", [
                ("Hạt nhựa PBT", 48, "kg", None),
            ])
            cursor.execute(
                "INSERT INTO production_info_loose_tube (roll_id, stt, fiber_code, shift, tube_code, "
                "machine_speed, color, fiber_count, diameter, bobbin_count, operator, notes) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (roll_id["OL-D2.5-24"], 1, "FB-0024", "Ca chiều", "OL-D2.5-24",
                 900.0, "Xanh lá", 24, 2.5, 24, uid["worker1"], "Đã hoàn thành đùn ống"),
            )
            add_log("OL-D2.5-24", "Đùn ống", "processing", "worker1", "Bắt đầu sản xuất")
            add_log("OL-D2.5-24", "Đùn ống", "pending-inspect", "worker1", "Đã hoàn thành, chuyển QC kiểm định")

            # ---------------- BOC-001 (pending-inspect) ----------------
            add_material_prep("BOC-001", "Chuẩn bị vật tư", "worker2", [
                ("Hạt nhựa HDPE", 75, "kg", None),
                ("Băng giáp thép", 2, "cuộn", None),
            ])
            cursor.execute(
                "INSERT INTO production_info_jacket (roll_id, product_code, error_roll_code, product_type, "
                "manufacture_date, operator, bl1, head_length, tail_length, notes) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (roll_id["BOC-001"], "BOC-001-SP", None, "Cáp quang bọc giáp", "2026-07-05",
                 uid["worker2"], "BL1-A", 5.0, 5.0, "Đã bọc xong, chờ kiểm định"),
            )
            add_log("BOC-001", "Bọc vỏ", "processing", "worker2", "Bắt đầu bọc vỏ")
            add_log("BOC-001", "Bọc vỏ", "pending-inspect", "worker2", "Hoàn thành, chuyển QC")

            # ---------------- SZ-002 (rejected) ----------------
            add_material_prep("SZ-002", "Chuẩn bị vật tư", "worker2", [
                ("Băng chặn nước", 4, "cuộn", None),
            ])
            cursor.execute(
                "INSERT INTO production_info_sz (roll_id, operator, notes) VALUES (%s, %s, %s)",
                (roll_id["SZ-002"], uid["worker2"], "Phát hiện lỗi bện lệch tâm"),
            )
            cursor.execute(
                "INSERT INTO qc_reports (roll_id, product_code, product_type, production_length, "
                "manufacture_date, quality_rating, short_fiber, broken_fiber, checked_date, checked_by, notes) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (roll_id["SZ-002"], "SZ-002-SP", "Bện SZ", 1750.0, "2026-07-05",
                 "Không đạt", 3, 2, now, uid["inspector"], "Lõi bện lệch tâm, yêu cầu sản xuất lại"),
            )
            add_log("SZ-002", "Bện SZ", "processing", "worker2", "Bắt đầu sản xuất")
            add_log("SZ-002", "Bện SZ", "pending-inspect", "worker2", "Chuyển QC kiểm định")
            add_log("SZ-002", "Bện SZ", "rejected", "inspector", "QC từ chối — lỗi bện lệch tâm")

            # ---------------- OL-D3.0-48 (completed) ----------------
            add_material_prep("OL-D3.0-48", "Chuẩn bị vật tư", "worker2", [
                ("Hạt nhựa PBT", 40, "kg", None),
                ("Sợi quang G652D", 48, "cuộn", None),
            ])
            cursor.execute(
                "INSERT INTO production_info_loose_tube (roll_id, stt, fiber_code, shift, tube_code, "
                "machine_speed, color, fiber_count, diameter, bobbin_count, operator, notes) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (roll_id["OL-D3.0-48"], 1, "FB-0048", "Ca sáng", "OL-D3.0-48",
                 870.0, "Tím", 48, 3.0, 48, uid["worker2"], "Hàng gấp, đã giao"),
            )
            cursor.execute(
                "INSERT INTO qc_reports (roll_id, product_code, product_type, production_length, "
                "manufacture_date, quality_rating, short_fiber, broken_fiber, checked_date, checked_by, notes) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (roll_id["OL-D3.0-48"], "OL-D3.0-48-SP", "Ống Lỏng", 1500.0, "2026-07-04",
                 "Đạt", 0, 0, now, uid["inspector"], "Đạt chuẩn, cho phép xuất kho"),
            )
            add_log("OL-D3.0-48", "Đùn ống", "processing", "worker2", "Bắt đầu sản xuất")
            add_log("OL-D3.0-48", "Đùn ống", "pending-inspect", "worker2", "Chuyển QC kiểm định")
            add_log("OL-D3.0-48", "Hoàn thành", "completed", "inspector", "QC duyệt đạt chuẩn")

            # =====================================================================
            # 3 LỆNH SẢN XUẤT THỰC TẾ — khớp chính xác 3 phiếu lệnh giấy đã cung cấp
            # =====================================================================

            # ---------------- LỆNH SX ỐNG LỎNG — Số: 59.2025 (khách hàng: Bộ Công An) ----------------
            add_material_prep("OL-59-2025", "Chuẩn bị vật tư", "worker1", [
                ("Hạt nhựa PBT", 120, "kg", None),
                ("Sợi quang G652D", 14, "cuộn", None),
            ])
            cursor.execute(
                "INSERT INTO plan_loose_tube (roll_id, operation_date, operator, fiber_count, diameter, notes, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (roll_id["OL-59-2025"], "2025-12-11", "worker1", 6, 2.05,
                 "XUẤT 5 BỘ 6C 48.8KM", "Chờ kiểm định"),
            )
            # 14 ống lỏng thành phẩm — đúng theo phiếu "LỆNH SẢN XUẤT ỐNG LỎNG Số: 59.2025"
            ol_59 = [
                (1, "OL-25-59-01", "Dương", 24400.0),
                (2, "OL-25-59-02", "Cam", 24400.0),
                (3, "OL-25-59-03", "Lục", 24400.0),
                (4, "OL-25-59-04", "Nâu", 12200.0),
                (5, "OL-25-59-05", "Nâu", 12200.0),
                (6, "OL-25-59-06", "Dương", 24400.0),
                (7, "OL-25-59-07", "Cam", 24400.0),
                (8, "OL-25-59-08", "Lục", 24400.0),
                (9, "OL-25-59-09", "Nâu", 12200.0),
                (10, "OL-25-59-10", "Nâu", 12200.0),
                (11, "OL-25-59-11", "Dương", 12200.0),
                (12, "OL-25-59-12", "Cam", 12200.0),
                (13, "OL-25-59-13", "Lục", 12200.0),
                (14, "OL-25-59-14", "Nâu", 12200.0),
            ]
            for stt, tube_code, color, length in ol_59:
                cursor.execute(
                    "INSERT INTO production_info_loose_tube (roll_id, stt, tube_code, color, fiber_count, "
                    "diameter, length, production_date, operator) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (roll_id["OL-59-2025"], stt, tube_code, color, 6, 2.05, length, "2025-12-11", uid["worker1"]),
                )
            add_log("OL-59-2025", "Đùn ống", "processing", "worker1", "Bắt đầu sản xuất theo lệnh 59.2025")
            add_log("OL-59-2025", "Đùn ống", "pending-inspect", "worker1", "Hoàn thành 14 ống lỏng, chuyển QC")

            # ---------------- LỆNH SX LÕI SZ — dùng chung số 59.2025 (khách hàng: BCA) ----------------
            add_material_prep("SZ-59-2025", "Chuẩn bị vật tư", "worker2", [
                ("Sợi filler", 5, "cuộn", None),
                ("Băng chặn nước", 5, "cuộn", None),
            ])
            cursor.execute(
                "INSERT INTO plan_sz (roll_id, operation_date, operator, fpr_type, binder_type, "
                "spec_summary, notes, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (roll_id["SZ-59-2025"], "2025-12-11", "worker2", "1*1500Dtex", "2*2000Dtex",
                 "DB 24C, 5 P.TỬ, FRP 1.7mm", "Bện từ 14 ống lỏng lệnh 59.2025", "Chờ kiểm định"),
            )
            # 5 lõi SZ, mỗi lõi bện từ 4 ống lỏng (Dương/Cam/Lục/Nâu) + filler — khớp phiếu "LỆNH SẢN XUẤT LÕI SZ"
            sz_59 = [
                (1, "SZ-25-59-01", 12200.0, "OL-25-59-01", "OL-25-59-02", "OL-25-59-03", "OL-25-59-04"),
                (2, "SZ-25-59-02", 12200.0, "OL-25-59-01", "OL-25-59-02", "OL-25-59-03", "OL-25-59-05"),
                (3, "SZ-25-59-03", 12200.0, "OL-25-59-06", "OL-25-59-07", "OL-25-59-08", "OL-25-59-09"),
                (4, "SZ-25-59-04", 12200.0, "OL-25-59-06", "OL-25-59-07", "OL-25-59-08", "OL-25-59-10"),
                (5, "SZ-25-59-05", 12200.0, "OL-25-59-11", "OL-25-59-12", "OL-25-59-13", "OL-25-59-14"),
            ]
            for stt, core_code, length, t_duong, t_cam, t_luc, t_nau in sz_59:
                cursor.execute(
                    "INSERT INTO production_info_sz (roll_id, stt, core_code, length, tube_duong, tube_cam, "
                    "tube_luc, tube_nau, filler, production_date, operator) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (roll_id["SZ-59-2025"], stt, core_code, length, t_duong, t_cam, t_luc, t_nau,
                     "Filler", "2025-12-11", uid["worker2"]),
                )
            add_log("SZ-59-2025", "Bện SZ", "processing", "worker2", "Bắt đầu bện 5 lõi SZ")
            add_log("SZ-59-2025", "Bện SZ", "pending-inspect", "worker2", "Hoàn thành 5 lõi SZ, chuyển QC")

            # ---------------- LỆNH SX BỌC VỎ CÁP — Số: 58.2025 (đơn hàng: VTVCAP) ----------------
            add_material_prep("BOC-58-2025", "Chuẩn bị vật tư", "worker2", [
                ("Hạt nhựa HDPE", 150, "kg", None),
                ("Thép treo 7x1.0mm", 3, "cuộn", None),
                ("Chỉ xé cáp", 1, "cuộn", None),
            ])
            cursor.execute(
                "INSERT INTO plan_jacket (roll_id, operation_date, operator, thickness, ripcord_count, "
                "hanging_steel, notes, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (roll_id["BOC-58-2025"], "2025-12-11", "worker2", 1.5, 1, "7x1.0mm",
                 "Bọc 1 — đơn hàng VTVCAP", "Chờ kiểm định"),
            )
            # 12 cuộn cáp thành phẩm — khớp phiếu "LỆNH SẢN XUẤT BỌC VỎ CÁP Số: 58.2025"
            boc_58 = [
                (1, "25-58-01", "SZ-25-58-01", "CVC VTVCAB ACF8 48FO 2025", 3.002),
                (2, "25-58-02", "SZ-25-58-02", "CVC VTVCAB DB 12FO 2025", 4.002),
                (3, "25-58-03", "SZ-25-58-02", "CVC VTVCAB DB 12FO 2025", 4.002),
                (4, "25-58-04", "SZ-25-58-02", "CVC VTVCAB DB 12FO 2025", 3.002),
                (5, "25-58-05", "SZ-votv tồn", "CVC VTVCAB DB 12FO 2025", 4.002),
                (6, "25-58-06", "SZ-votv tồn", "CVC VTVCAB DB 12FO 2025", 4.002),
                (7, "25-58-07", "SZ-votv tồn", "CVC VTVCAB DB 12FO 2025", 4.002),
                (8, "25-58-08", "SZ-votv tồn", "CVC VTVCAB DB 12FO 2025", 4.002),
                (9, "25-58-09", "SZ-votv tồn", "CVC VTVCAB DB 12FO 2025", 3.002),
                (10, "25-58-10", "SZ-25-58-03", "CVC VTVCAB DB 24FO 2025", 3.002),
                (11, "25-58-11", "SZ-25-58-03", "CVC VTVCAB DB 24FO 2025", 3.002),
                (12, "25-58-12", "SZ-25-58-04", "CVC VTVCAB DB 24FO 2025", 4.002),
            ]
            for stt, cable_code, core_code, label, length in boc_58:
                cursor.execute(
                    "INSERT INTO production_info_jacket (roll_id, stt, cable_code, core_code, product_label, "
                    "length, manufacture_date, operator) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (roll_id["BOC-58-2025"], stt, cable_code, core_code, label, length,
                     "2025-12-11", uid["worker2"]),
                )
            add_log("BOC-58-2025", "Bọc vỏ", "processing", "worker2", "Bắt đầu bọc vỏ cáp 58.2025")
            add_log("BOC-58-2025", "Bọc vỏ", "pending-inspect", "worker2", "Hoàn thành 12 cuộn cáp, chuyển QC")

        conn.commit()

    # ================= USERS =================

    def get_user(self, username):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
                return cursor.fetchone()
        finally:
            conn.close()

    def get_users(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT username, role, full_name, department FROM users ORDER BY username")
                return cursor.fetchall()
        finally:
            conn.close()

    def create_user(self, username, password_hash, role):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                    (username, password_hash, role),
                )
            conn.commit()
        finally:
            conn.close()

    def delete_user(self, username):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE username=%s AND username<>'admin'", (username,))
            conn.commit()
        finally:
            conn.close()

    def change_password(self, username, password_hash):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET password_hash=%s WHERE username=%s",
                    (password_hash, username),
                )
            conn.commit()
        finally:
            conn.close()

    # ================= CABLE ROLLS (danh sách theo tab) =================

    def get_rolls(self, tab, role, username):
        """
        Trả về danh sách cable_rolls cho 1 tab, join contracts + operator gần nhất
        (lấy từ production_logs.updated_by mới nhất) + qc_reports (cho tab rejected).
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        cr.id, cr.roll_code, cr.product_type, cr.length,
                        cr.current_stage, cr.status, cr.created_at,
                        cr.in_inventory, cr.checklist_status,
                        c.id AS contract_id, c.contract_code, c.customer_name,
                        c.requester, c.approver, c.created_date,
                        (SELECT u.username FROM production_logs pl
                            JOIN users u ON u.id = pl.updated_by
                            WHERE pl.roll_id = cr.id
                            ORDER BY pl.updated_at DESC LIMIT 1) AS operator
                    FROM cable_rolls cr
                    JOIN contracts c ON c.id = cr.contract_id
                    WHERE cr.status = %s
                    ORDER BY cr.created_at DESC
                    """,
                    (tab,),
                )
                rows = cursor.fetchall()

                # Người không phải admin/inspector: chỉ thấy phiếu đang chờ (chưa ai nhận)
                # hoặc phiếu chính họ đang xử lý.
                if role not in ("admin", "inspector"):
                    if tab == "pending":
                        pass  # ai cũng thấy việc đang chờ để nhận
                    else:
                        rows = [r for r in rows if r["operator"] == username]

                result = []
                for r in rows:
                    item = {
                        "id": r["id"],
                        "roll_code": r["roll_code"],
                        "product_type": r["product_type"],
                        "length": r["length"],
                        "current_stage": r["current_stage"],
                        "status": r["status"],
                        "created_at": str(r["created_at"]) if r["created_at"] else None,
                        "operator": r["operator"],
                        "contract": {
                            "id": r["contract_id"],
                            "contract_code": r["contract_code"],
                            "customer_name": r["customer_name"],
                            "requester": r["requester"],
                            "approver": r["approver"],
                            "created_date": str(r["created_date"]) if r["created_date"] else None,
                        },
                    }

                    if tab == "rejected":
                        cursor.execute(
                            "SELECT quality_rating, checked_date FROM qc_reports "
                            "WHERE roll_id=%s ORDER BY id DESC LIMIT 1",
                            (r["id"],),
                        )
                        qc = cursor.fetchone()
                        item["qc"] = {
                            "quality_rating": qc["quality_rating"],
                            "checked_date": str(qc["checked_date"]) if qc and qc["checked_date"] else None,
                        } if qc else None

                        # Thêm thông tin checklist/inventory nếu có
                        item["in_inventory"] = bool(r.get("in_inventory")) if r.get("in_inventory") is not None else False
                        item["checklist_status"] = r.get("checklist_status")

                    result.append(item)

                # Với các tab khác cũng trả checklist/inventory để frontend hiển thị
                for r_item in result:
                    if "in_inventory" not in r_item:
                        r_item["in_inventory"] = bool(r_item.get("in_inventory")) if r_item.get("in_inventory") is not None else False
                    if "checklist_status" not in r_item:
                        r_item["checklist_status"] = r_item.get("checklist_status")

                return result
        finally:
            conn.close()

    def get_loose_tube_form_by_roll(self, roll_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT lf.*, u.username AS operator_name "
                    "FROM loose_tube_forms lf "
                    "LEFT JOIN users u ON u.id = lf.operator "
                    "WHERE lf.roll_id=%s",
                    (roll_id,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def get_sz_form_by_roll(self, roll_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT f.*, u.username AS operator_name "
                    "FROM sz_production_forms f "
                    "LEFT JOIN users u ON u.id = f.operator "
                    "WHERE f.roll_id=%s",
                    (roll_id,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def get_jacket_form_by_roll(self, roll_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT f.*, u.username AS operator_name "
                    "FROM jacket_production_forms f "
                    "LEFT JOIN users u ON u.id = f.operator "
                    "WHERE f.roll_id=%s",
                    (roll_id,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def get_jacket_kcs_form_by_roll(self, roll_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT f.*, u.username AS operator_name "
                    "FROM jacket_kcs_forms f "
                    "LEFT JOIN users u ON u.id = f.operator "
                    "WHERE f.roll_id=%s",
                    (roll_id,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def get_loose_tube_form_by_id(self, form_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT lf.*, u.username AS operator_name, cr.roll_code, c.contract_code, c.customer_name "
                    "FROM loose_tube_forms lf "
                    "JOIN cable_rolls cr ON cr.id = lf.roll_id "
                    "JOIN contracts c ON c.id = cr.contract_id "
                    "LEFT JOIN users u ON u.id = lf.operator "
                    "WHERE lf.id=%s",
                    (form_id,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def get_sz_form_by_id(self, form_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT f.*, u.username AS operator_name, cr.roll_code, c.contract_code, c.customer_name "
                    "FROM sz_production_forms f "
                    "JOIN cable_rolls cr ON cr.id = f.roll_id "
                    "JOIN contracts c ON c.id = cr.contract_id "
                    "LEFT JOIN users u ON u.id = f.operator "
                    "WHERE f.id=%s",
                    (form_id,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def get_jacket_form_by_id(self, form_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT f.*, u.username AS operator_name, cr.roll_code, c.contract_code, c.customer_name "
                    "FROM jacket_production_forms f "
                    "JOIN cable_rolls cr ON cr.id = f.roll_id "
                    "JOIN contracts c ON c.id = cr.contract_id "
                    "LEFT JOIN users u ON u.id = f.operator "
                    "WHERE f.id=%s",
                    (form_id,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def get_jacket_kcs_form_by_id(self, form_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT f.*, u.username AS operator_name, cr.roll_code, c.contract_code, c.customer_name "
                    "FROM jacket_kcs_forms f "
                    "JOIN cable_rolls cr ON cr.id = f.roll_id "
                    "JOIN contracts c ON c.id = cr.contract_id "
                    "LEFT JOIN users u ON u.id = f.operator "
                    "WHERE f.id=%s",
                    (form_id,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def create_loose_tube_form(self, roll_id, data, username):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, status, product_type FROM cable_rolls WHERE id=%s", (roll_id,))
                roll = cursor.fetchone()
                if not roll or roll["product_type"] != "loose_tube":
                    return False

                cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
                user = cursor.fetchone()
                operator_id = user["id"] if user else None

                production_date = data.get("production_date") or None
                if production_date:
                    production_date = datetime.fromisoformat(production_date).date()

                cursor.execute("SELECT id FROM loose_tube_forms WHERE roll_id=%s", (roll_id,))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute(
                        "UPDATE loose_tube_forms SET stt=%s, fiber_code=%s, shift=%s, tube_code=%s, "
                        "machine_speed=%s, color=%s, fiber_count=%s, diameter=%s, length=%s, "
                        "production_date=%s, bobbin_count=%s, operator=%s, notes=%s, form_status=%s "
                        "WHERE roll_id=%s",
                        (
                            data.get("stt"),
                            data.get("fiber_code"),
                            data.get("shift"),
                            data.get("tube_code"),
                            data.get("machine_speed"),
                            data.get("color"),
                            data.get("fiber_count"),
                            data.get("diameter"),
                            data.get("length"),
                            production_date,
                            data.get("bobbin_count"),
                            operator_id,
                            data.get("notes"),
                            "Đã nhập",
                            roll_id,
                        ),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO loose_tube_forms (roll_id, stt, fiber_code, shift, tube_code, machine_speed, "
                        "color, fiber_count, diameter, length, production_date, bobbin_count, operator, notes, form_status) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            roll_id,
                            data.get("stt"),
                            data.get("fiber_code"),
                            data.get("shift"),
                            data.get("tube_code"),
                            data.get("machine_speed"),
                            data.get("color"),
                            data.get("fiber_count"),
                            data.get("diameter"),
                            data.get("length"),
                            production_date,
                            data.get("bobbin_count"),
                            operator_id,
                            data.get("notes"),
                            "Đã nhập",
                        ),
                    )

                if roll["status"] == "pending":
                    cursor.execute(
                        "UPDATE cable_rolls SET status=%s WHERE id=%s",
                        ("processing", roll_id),
                    )

                cursor.execute(
                    "INSERT INTO production_logs (roll_id, stage, status, updated_by, updated_at, notes) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (roll_id, "Đùn ống", "Đã nhập", operator_id, datetime.now(), "Lưu phiếu thông tin ống lỏng"),
                )
            conn.commit()
            return True
        finally:
            conn.close()

    def create_sz_form(self, roll_id, data, username):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, status, product_type FROM cable_rolls WHERE id=%s", (roll_id,))
                roll = cursor.fetchone()
                if not roll or roll["product_type"] != "sz":
                    return False

                cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
                user = cursor.fetchone()
                operator_id = user["id"] if user else None

                production_date = data.get("production_date") or None
                if production_date:
                    production_date = datetime.fromisoformat(production_date).date()

                cursor.execute("SELECT id FROM sz_production_forms WHERE roll_id=%s", (roll_id,))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute(
                        "UPDATE sz_production_forms SET stt=%s, product_code=%s, core_code=%s, shift=%s, production_date=%s, machine=%s, machine_speed=%s, length=%s, sz_pitch=%s, lay_direction=%s, tension=%s, pull_speed=%s, post_braid_diameter=%s, kcs_diameter=%s, kcs_uniformity=%s, kcs_external_inspection=%s, kcs_notes=%s, operator=%s, notes=%s, form_status=%s WHERE roll_id=%s",
                        (
                            data.get("stt"),
                            data.get("product_code"),
                            data.get("core_code"),
                            data.get("shift"),
                            production_date,
                            data.get("machine"),
                            data.get("machine_speed"),
                            data.get("length"),
                            data.get("sz_pitch"),
                            data.get("lay_direction"),
                            data.get("tension"),
                            data.get("pull_speed"),
                            data.get("post_braid_diameter"),
                            data.get("kcs_diameter"),
                            data.get("kcs_uniformity"),
                            data.get("kcs_external_inspection"),
                            data.get("kcs_notes"),
                            operator_id,
                            data.get("notes"),
                            "Đã nhập",
                            roll_id,
                        ),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO sz_production_forms (roll_id, stt, product_code, core_code, shift, production_date, machine, machine_speed, length, sz_pitch, lay_direction, tension, pull_speed, post_braid_diameter, kcs_diameter, kcs_uniformity, kcs_external_inspection, kcs_notes, operator, notes, form_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            roll_id,
                            data.get("stt"),
                            data.get("product_code"),
                            data.get("core_code"),
                            data.get("shift"),
                            production_date,
                            data.get("machine"),
                            data.get("machine_speed"),
                            data.get("length"),
                            data.get("sz_pitch"),
                            data.get("lay_direction"),
                            data.get("tension"),
                            data.get("pull_speed"),
                            data.get("post_braid_diameter"),
                            data.get("kcs_diameter"),
                            data.get("kcs_uniformity"),
                            data.get("kcs_external_inspection"),
                            data.get("kcs_notes"),
                            operator_id,
                            data.get("notes"),
                            "Đã nhập",
                        ),
                    )

                if roll["status"] == "pending":
                    cursor.execute("UPDATE cable_rolls SET status=%s WHERE id=%s", ("processing", roll_id))

                cursor.execute(
                    "INSERT INTO production_logs (roll_id, stage, status, updated_by, updated_at, notes) VALUES (%s, %s, %s, %s, %s, %s)",
                    (roll_id, "Bện SZ", "Đã nhập", operator_id, datetime.now(), "Lưu phiếu thông tin bện SZ"),
                )
            conn.commit()
            return True
        finally:
            conn.close()

    def create_jacket_form(self, roll_id, data, username):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, status, product_type FROM cable_rolls WHERE id=%s", (roll_id,))
                roll = cursor.fetchone()
                if not roll or roll["product_type"] != "jacket":
                    return False

                cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
                user = cursor.fetchone()
                operator_id = user["id"] if user else None

                manufacture_date = data.get("manufacture_date") or None
                if manufacture_date:
                    manufacture_date = datetime.fromisoformat(manufacture_date).date()

                cursor.execute("SELECT id FROM jacket_production_forms WHERE roll_id=%s", (roll_id,))
                existing = cursor.fetchone()
                kcs_measurements = data.get("kcs_measurements")
                if kcs_measurements is not None and not isinstance(kcs_measurements, str):
                    kcs_measurements = json.dumps(kcs_measurements, ensure_ascii=False)

                if existing:
                    cursor.execute(
                        "UPDATE jacket_production_forms SET stt=%s, cable_code=%s, core_code=%s, product_label=%s, length=%s, product_type=%s, shift=%s, manufacture_date=%s, bin=%s, frp=%s, bl1=%s, head_length=%s, tail_length=%s, kcs_measurements=%s, measured_length=%s, loss_result=%s, measured_by=%s, operator=%s, notes=%s, form_status=%s WHERE roll_id=%s",
                        (
                            data.get("stt"),
                            data.get("cable_code"),
                            data.get("core_code"),
                            data.get("product_label"),
                            data.get("length"),
                            data.get("product_type"),
                            data.get("shift"),
                            manufacture_date,
                            data.get("bin"),
                            data.get("frp"),
                            data.get("bl1"),
                            data.get("head_length"),
                            data.get("tail_length"),
                            kcs_measurements,
                            data.get("measured_length"),
                            data.get("loss_result"),
                            data.get("measured_by"),
                            operator_id,
                            data.get("notes"),
                            "Đã nhập",
                            roll_id,
                        ),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO jacket_production_forms (roll_id, stt, cable_code, core_code, product_label, length, product_type, shift, manufacture_date, bin, frp, bl1, head_length, tail_length, kcs_measurements, measured_length, loss_result, measured_by, operator, notes, form_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            roll_id,
                            data.get("stt"),
                            data.get("cable_code"),
                            data.get("core_code"),
                            data.get("product_label"),
                            data.get("length"),
                            data.get("product_type"),
                            data.get("shift"),
                            manufacture_date,
                            data.get("bin"),
                            data.get("frp"),
                            data.get("bl1"),
                            data.get("head_length"),
                            data.get("tail_length"),
                            kcs_measurements,
                            data.get("measured_length"),
                            data.get("loss_result"),
                            data.get("measured_by"),
                            operator_id,
                            data.get("notes"),
                            "Đã nhập",
                        ),
                    )

                if roll["status"] == "pending":
                    cursor.execute("UPDATE cable_rolls SET status=%s WHERE id=%s", ("processing", roll_id))

                cursor.execute(
                    "INSERT INTO production_logs (roll_id, stage, status, updated_by, updated_at, notes) VALUES (%s, %s, %s, %s, %s, %s)",
                    (roll_id, "Bọc vỏ", "Đã nhập", operator_id, datetime.now(), "Lưu phiếu thông tin bọc vỏ"),
                )
            conn.commit()
            return True
        finally:
            conn.close()

    def create_jacket_kcs_form(self, roll_id, data, username):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, status, product_type FROM cable_rolls WHERE id=%s", (roll_id,))
                roll = cursor.fetchone()
                if not roll or roll["product_type"] != "jacket":
                    return False

                cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
                user = cursor.fetchone()
                operator_id = user["id"] if user else None

                manufacture_date = data.get("manufacture_date") or None
                if manufacture_date:
                    manufacture_date = datetime.fromisoformat(manufacture_date).date()

                cursor.execute("SELECT id FROM jacket_kcs_forms WHERE roll_id=%s", (roll_id,))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute(
                        "UPDATE jacket_kcs_forms SET stt=%s, cable_code=%s, core_code=%s, product_label=%s, length=%s, product_type=%s, error_roll_code=%s, manufacture_date=%s, inspection_result=%s, inspection_notes=%s, operator=%s, notes=%s, form_status=%s WHERE roll_id=%s",
                        (
                            data.get("stt"),
                            data.get("cable_code"),
                            data.get("core_code"),
                            data.get("product_label"),
                            data.get("length"),
                            data.get("product_type"),
                            data.get("error_roll_code"),
                            manufacture_date,
                            data.get("inspection_result"),
                            data.get("inspection_notes"),
                            operator_id,
                            data.get("notes"),
                            "Đã nhập",
                            roll_id,
                        ),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO jacket_kcs_forms (roll_id, stt, cable_code, core_code, product_label, length, product_type, error_roll_code, manufacture_date, inspection_result, inspection_notes, operator, notes, form_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            roll_id,
                            data.get("stt"),
                            data.get("cable_code"),
                            data.get("core_code"),
                            data.get("product_label"),
                            data.get("length"),
                            data.get("product_type"),
                            data.get("error_roll_code"),
                            manufacture_date,
                            data.get("inspection_result"),
                            data.get("inspection_notes"),
                            operator_id,
                            data.get("notes"),
                            "Đã nhập",
                        ),
                    )

                if roll["status"] == "pending":
                    cursor.execute("UPDATE cable_rolls SET status=%s WHERE id=%s", ("processing", roll_id))

                cursor.execute(
                    "INSERT INTO production_logs (roll_id, stage, status, updated_by, updated_at, notes) VALUES (%s, %s, %s, %s, %s, %s)",
                    (roll_id, "KCS Bọc vỏ", "Đã nhập", operator_id, datetime.now(), "Lưu phiếu thông tin KCS bọc vỏ"),
                )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_loose_tube_forms(self, roll_code=None, contract_code=None, worker=None, production_date=None, shift=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = (
                    "SELECT lf.id, cr.roll_code, c.contract_code, c.customer_name, lf.shift, lf.production_date, "
                    "u.username AS worker, lf.form_status, lf.created_at, lf.updated_at "
                    "FROM loose_tube_forms lf "
                    "JOIN cable_rolls cr ON cr.id = lf.roll_id "
                    "JOIN contracts c ON c.id = cr.contract_id "
                    "LEFT JOIN users u ON u.id = lf.operator "
                    "WHERE 1=1"
                )
                params = []
                if roll_code:
                    query += " AND cr.roll_code LIKE %s"
                    params.append(f"%{roll_code}%")
                if contract_code:
                    query += " AND c.contract_code LIKE %s"
                    params.append(f"%{contract_code}%")
                if worker:
                    query += " AND u.username LIKE %s"
                    params.append(f"%{worker}%")
                if production_date:
                    query += " AND lf.production_date = %s"
                    params.append(production_date)
                if shift:
                    query += " AND lf.shift LIKE %s"
                    params.append(f"%{shift}%")

                query += " ORDER BY lf.updated_at DESC"
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                for r in rows:
                    if r.get("production_date"):
                        r["production_date"] = str(r["production_date"])
                    if r.get("created_at"):
                        r["created_at"] = str(r["created_at"])
                    if r.get("updated_at"):
                        r["updated_at"] = str(r["updated_at"])
                return rows
        finally:
            conn.close()

    def get_sz_forms(self, roll_code=None, contract_code=None, worker=None, production_date=None, shift=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = (
                    "SELECT f.id, cr.roll_code, c.contract_code, c.customer_name, f.shift, f.production_date, "
                    "u.username AS worker, f.form_status, f.created_at, f.updated_at "
                    "FROM sz_production_forms f "
                    "JOIN cable_rolls cr ON cr.id = f.roll_id "
                    "JOIN contracts c ON c.id = cr.contract_id "
                    "LEFT JOIN users u ON u.id = f.operator "
                    "WHERE 1=1"
                )
                params = []
                if roll_code:
                    query += " AND cr.roll_code LIKE %s"
                    params.append(f"%{roll_code}%")
                if contract_code:
                    query += " AND c.contract_code LIKE %s"
                    params.append(f"%{contract_code}%")
                if worker:
                    query += " AND u.username LIKE %s"
                    params.append(f"%{worker}%")
                if production_date:
                    query += " AND f.production_date = %s"
                    params.append(production_date)
                if shift:
                    query += " AND f.shift LIKE %s"
                    params.append(f"%{shift}%")

                query += " ORDER BY f.updated_at DESC"
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                for r in rows:
                    if r.get("production_date"):
                        r["production_date"] = str(r["production_date"])
                    if r.get("created_at"):
                        r["created_at"] = str(r["created_at"])
                    if r.get("updated_at"):
                        r["updated_at"] = str(r["updated_at"])
                return rows
        finally:
            conn.close()

    def get_jacket_forms(self, roll_code=None, contract_code=None, worker=None, production_date=None, shift=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = (
                    "SELECT f.id, cr.roll_code, c.contract_code, c.customer_name, f.shift, f.manufacture_date AS production_date, "
                    "u.username AS worker, f.form_status, f.created_at, f.updated_at "
                    "FROM jacket_production_forms f "
                    "JOIN cable_rolls cr ON cr.id = f.roll_id "
                    "JOIN contracts c ON c.id = cr.contract_id "
                    "LEFT JOIN users u ON u.id = f.operator "
                    "WHERE 1=1"
                )
                params = []
                if roll_code:
                    query += " AND cr.roll_code LIKE %s"
                    params.append(f"%{roll_code}%")
                if contract_code:
                    query += " AND c.contract_code LIKE %s"
                    params.append(f"%{contract_code}%")
                if worker:
                    query += " AND u.username LIKE %s"
                    params.append(f"%{worker}%")
                if production_date:
                    query += " AND f.manufacture_date = %s"
                    params.append(production_date)
                if shift:
                    query += " AND 1=0"

                query += " ORDER BY f.updated_at DESC"
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                for r in rows:
                    if r.get("production_date"):
                        r["production_date"] = str(r["production_date"])
                    if r.get("created_at"):
                        r["created_at"] = str(r["created_at"])
                    if r.get("updated_at"):
                        r["updated_at"] = str(r["updated_at"])
                return rows
        finally:
            conn.close()

    def get_jacket_kcs_forms(self, roll_code=None, contract_code=None, worker=None, production_date=None, shift=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = (
                    "SELECT f.id, cr.roll_code, c.contract_code, c.customer_name, NULL AS shift, f.manufacture_date AS production_date, "
                    "u.username AS worker, f.form_status, f.created_at, f.updated_at "
                    "FROM jacket_kcs_forms f "
                    "JOIN cable_rolls cr ON cr.id = f.roll_id "
                    "JOIN contracts c ON c.id = cr.contract_id "
                    "LEFT JOIN users u ON u.id = f.operator "
                    "WHERE 1=1"
                )
                params = []
                if roll_code:
                    query += " AND cr.roll_code LIKE %s"
                    params.append(f"%{roll_code}%")
                if contract_code:
                    query += " AND c.contract_code LIKE %s"
                    params.append(f"%{contract_code}%")
                if worker:
                    query += " AND u.username LIKE %s"
                    params.append(f"%{worker}%")
                if production_date:
                    query += " AND f.manufacture_date = %s"
                    params.append(production_date)
                if shift:
                    query += " AND 1=0"

                query += " ORDER BY f.updated_at DESC"
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                for r in rows:
                    if r.get("production_date"):
                        r["production_date"] = str(r["production_date"])
                    if r.get("created_at"):
                        r["created_at"] = str(r["created_at"])
                    if r.get("updated_at"):
                        r["updated_at"] = str(r["updated_at"])
                return rows
        finally:
            conn.close()

    # ================= CHI TIẾT 1 LÔ (roll) =================

    def get_roll_detail(self, roll_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM cable_rolls WHERE id=%s", (roll_id,))
                roll = cursor.fetchone()
                if not roll:
                    return None

                cursor.execute("SELECT * FROM contracts WHERE id=%s", (roll["contract_id"],))
                contract = cursor.fetchone()

                # Chuẩn bị vật tư + items
                cursor.execute(
                    "SELECT * FROM material_preparations WHERE roll_id=%s ORDER BY id DESC LIMIT 1",
                    (roll_id,),
                )
                prep = cursor.fetchone()
                if prep:
                    cursor.execute(
                        "SELECT id, item_name, quantity, unit, notes "
                        "FROM material_preparation_items WHERE preparation_id=%s",
                        (prep["id"],),
                    )
                    prep["items"] = cursor.fetchall()

                # Thông tin sản xuất thực tế (bảng khác nhau theo product_type)
                production_info = []
                table = PRODUCTION_TABLE_BY_TYPE.get(roll["product_type"])
                if table:
                    cursor.execute(f"SELECT * FROM {table} WHERE roll_id=%s ORDER BY id", (roll_id,))
                    production_info = cursor.fetchall()

                # Thông số kỹ thuật / kế hoạch (plan_loose_tube / plan_sz / plan_jacket)
                plan = None
                plan_table = PLAN_TABLE_BY_TYPE.get(roll["product_type"])
                if plan_table:
                    cursor.execute(f"SELECT * FROM {plan_table} WHERE roll_id=%s ORDER BY id DESC LIMIT 1", (roll_id,))
                    plan = cursor.fetchone()

                # QC
                cursor.execute(
                    "SELECT * FROM qc_reports WHERE roll_id=%s ORDER BY id DESC LIMIT 1",
                    (roll_id,),
                )
                qc_report = cursor.fetchone()

                # Form sản xuất thực tế theo từng loại
                production_form = None
                if roll["product_type"] == "loose_tube":
                    production_form = self.get_loose_tube_form_by_roll(roll_id)
                elif roll["product_type"] == "sz":
                    production_form = self.get_sz_form_by_roll(roll_id)
                elif roll["product_type"] == "jacket":
                    production_form = self.get_jacket_form_by_roll(roll_id)
                    if not production_form:
                        production_form = self.get_jacket_kcs_form_by_roll(roll_id)

                # Inventory / warehouse record (nếu đã nhập kho)
                cursor.execute(
                    "SELECT * FROM inventory WHERE roll_id=%s ORDER BY id DESC LIMIT 1",
                    (roll_id,),
                )
                inventory = cursor.fetchone()

                # Lịch sử cập nhật
                cursor.execute(
                    """
                    SELECT pl.stage, pl.status, pl.updated_at, pl.notes, u.username AS updated_by
                    FROM production_logs pl
                    LEFT JOIN users u ON u.id = pl.updated_by
                    WHERE pl.roll_id=%s
                    ORDER BY pl.updated_at DESC
                    """,
                    (roll_id,),
                )
                logs = cursor.fetchall()

                def stringify_dates(d):
                    for k, v in d.items():
                        if hasattr(v, "isoformat"):
                            d[k] = str(v)
                    return d

                result = {
                    "roll": stringify_dates(dict(roll)),
                    "inventory": stringify_dates(dict(inventory)) if inventory else None,
                    "contract": stringify_dates(dict(contract)) if contract else None,
                    "material_preparation": stringify_dates(dict(prep)) if prep else None,
                    "plan": stringify_dates(dict(plan)) if plan else None,
                    "production_info": [stringify_dates(dict(r)) for r in production_info],
                    "qc_report": stringify_dates(dict(qc_report)) if qc_report else None,
                    "production_form": stringify_dates(dict(production_form)) if production_form else None,
                    "logs": [stringify_dates(dict(l)) for l in logs],
                }

                if roll["product_type"] == "loose_tube":
                    result["loose_tube_form"] = stringify_dates(dict(production_form)) if production_form else None

                return result
        finally:
            conn.close()

    # ================= CẬP NHẬT TRẠNG THÁI =================

    def get_roll_status(self, roll_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, status, current_stage FROM cable_rolls WHERE id=%s", (roll_id,))
                return cursor.fetchone()
        finally:
            conn.close()

    def update_roll_status(self, roll_id, new_status, username):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT current_stage FROM cable_rolls WHERE id=%s", (roll_id,))
                roll = cursor.fetchone()
                if not roll:
                    return False

                cursor.execute(
                    "UPDATE cable_rolls SET status=%s WHERE id=%s",
                    (new_status, roll_id),
                )

                cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
                user = cursor.fetchone()
                user_id = user["id"] if user else None

                cursor.execute(
                    """
                    INSERT INTO production_logs (roll_id, stage, status, updated_by, updated_at, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (roll_id, roll["current_stage"], new_status, user_id, datetime.now(), None),
                )
            conn.commit()
            return True
        finally:
            conn.close()

    def submit_qc_report(self, roll_id, data, username):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, status, current_stage FROM cable_rolls WHERE id=%s", (roll_id,))
                roll = cursor.fetchone()
                if not roll:
                    return False

                cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
                user = cursor.fetchone()
                checked_by = user["id"] if user else None

                manufacture_date = data.get("manufacture_date") or None
                if manufacture_date:
                    manufacture_date = datetime.fromisoformat(manufacture_date).date()

                checked_date = data.get("checked_date") or None
                if checked_date:
                    checked_date = datetime.fromisoformat(checked_date)
                else:
                    checked_date = datetime.now()

                quality_rating = data.get("quality_rating")
                new_status = "completed" if quality_rating == "Đạt" else "rejected"
                new_stage = "Hoàn thành" if quality_rating == "Đạt" else "Yêu cầu làm lại"

                cursor.execute(
                    """
                    INSERT INTO qc_reports (
                        roll_id, product_code, product_type, production_length,
                        manufacture_date, quality_rating, short_fiber, broken_fiber,
                        checked_date, checked_by, shift, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        roll_id,
                        data.get("product_code"),
                        data.get("product_type"),
                        data.get("production_length"),
                        manufacture_date,
                        quality_rating,
                        data.get("short_fiber"),
                        data.get("broken_fiber"),
                        checked_date,
                        checked_by,
                        data.get("shift"),
                        data.get("notes"),
                    ),
                )

                cursor.execute(
                    "UPDATE cable_rolls SET status=%s, current_stage=%s WHERE id=%s",
                    (new_status, new_stage, roll_id),
                )

                cursor.execute(
                    """
                    INSERT INTO production_logs (roll_id, stage, status, updated_by, updated_at, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (roll_id, roll["current_stage"] or "QC", new_status, checked_by, datetime.now(), f"QC: {quality_rating}"),
                )

                # Nếu QC 'Đạt' -> nhập kho tự động + cập nhật checklist
                if quality_rating == "Đạt":
                    product_code = data.get("product_code") or None
                    product_type = data.get("product_type") or roll.get("product_type")
                    prod_length = data.get("production_length") or roll.get("length")

                    cursor.execute(
                        "INSERT INTO inventory (roll_id, product_code, product_type, length, quantity, location, status, notes)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (roll_id, product_code, product_type, prod_length, 1, "Kho chính", "in_stock",
                         "Tự động nhập kho khi QC duyệt đạt"),
                    )

                    cursor.execute(
                        "UPDATE cable_rolls SET in_inventory=1, checklist_status=%s WHERE id=%s",
                        ("Hoàn thành/Chờ giao", roll_id),
                    )
            conn.commit()
            return True
        finally:
            conn.close()

    # ================= NHẬT KÝ THAO TÁC (AUDIT LOG) =================

    def add_audit_log(self, username, role, action, target=None, description=None):
        """Ghi lại 1 thao tác của bất kỳ role nào (đăng nhập, đổi mật khẩu,
        cập nhật trạng thái lô, tạo/xóa tài khoản...). Không raise lỗi ra
        ngoài để việc ghi log không bao giờ làm hỏng luồng chính."""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO audit_logs (username, role, action, target, description, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (username, role, action, target, description, datetime.now()),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

    def get_audit_logs(self, role=None, limit=200):
        """Trả về danh sách nhật ký thao tác, mới nhất trước.
        role=None -> tất cả role. role='worker1' -> chỉ role đó, v.v."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                if role and role != "all":
                    cursor.execute(
                        "SELECT * FROM audit_logs WHERE role=%s ORDER BY created_at DESC LIMIT %s",
                        (role, limit),
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT %s",
                        (limit,),
                    )
                rows = cursor.fetchall()
                for r in rows:
                    if r.get("created_at"):
                        r["created_at"] = str(r["created_at"])
                return rows
        finally:
            conn.close()


db = Database()
