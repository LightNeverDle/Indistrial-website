-- =====================================================================
-- SMART FACTORY — SCHEMA MySQL CHUẨN HÓA
-- Khớp với factory_management.sql (bảng trung tâm: cable_rolls)
-- Backend (database.py) tự chạy file này khi khởi động nếu bảng chưa có.
-- =====================================================================

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  full_name VARCHAR(100) DEFAULT NULL,
  role VARCHAR(50) DEFAULT NULL,
  department VARCHAR(50) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS contracts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  contract_code VARCHAR(50) NOT NULL UNIQUE,
  customer_name VARCHAR(255) NOT NULL,
  requester VARCHAR(100) DEFAULT NULL,
  approver VARCHAR(100) DEFAULT NULL,
  created_date DATE DEFAULT NULL,
  status VARCHAR(50) DEFAULT NULL,
  notes TEXT DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- product_type: 'loose_tube' | 'sz' | 'jacket'  (khớp PRODUCT_LABELS ở frontend)
-- status: 'pending' | 'processing' | 'pending-inspect' | 'rejected' | 'completed'
CREATE TABLE IF NOT EXISTS cable_rolls (
  id INT AUTO_INCREMENT PRIMARY KEY,
  contract_id INT NOT NULL,
  roll_code VARCHAR(50) NOT NULL UNIQUE,
  product_type VARCHAR(50) DEFAULT NULL,
  length FLOAT DEFAULT NULL,
  current_stage VARCHAR(50) DEFAULT NULL,
  status VARCHAR(50) DEFAULT 'pending',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_cable_rolls_contract FOREIGN KEY (contract_id) REFERENCES contracts(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS material_preparations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  roll_id INT NOT NULL,
  stage VARCHAR(50) DEFAULT NULL,
  prepared_by INT DEFAULT NULL,
  prepared_date DATETIME DEFAULT NULL,
  status VARCHAR(50) DEFAULT NULL,
  CONSTRAINT fk_matprep_roll FOREIGN KEY (roll_id) REFERENCES cable_rolls(id),
  CONSTRAINT fk_matprep_user FOREIGN KEY (prepared_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS material_preparation_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  preparation_id INT NOT NULL,
  item_name VARCHAR(100) DEFAULT NULL,
  quantity FLOAT DEFAULT NULL,
  unit VARCHAR(20) DEFAULT NULL,
  notes TEXT DEFAULT NULL,
  CONSTRAINT fk_matitem_prep FOREIGN KEY (preparation_id) REFERENCES material_preparations(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS plan_loose_tube (
  id INT AUTO_INCREMENT PRIMARY KEY,
  roll_id INT NOT NULL,
  operation_date DATE DEFAULT NULL,
  start_time TIME DEFAULT NULL,
  end_time TIME DEFAULT NULL,
  operator VARCHAR(100) DEFAULT NULL,
  tube_color VARCHAR(50) DEFAULT NULL,
  fiber_count INT DEFAULT NULL,
  diameter FLOAT DEFAULT NULL,
  length FLOAT DEFAULT NULL,
  notes TEXT DEFAULT NULL,
  status VARCHAR(50) DEFAULT NULL,
  CONSTRAINT fk_plan_lt_roll FOREIGN KEY (roll_id) REFERENCES cable_rolls(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS plan_sz (
  id INT AUTO_INCREMENT PRIMARY KEY,
  roll_id INT NOT NULL,
  operation_date DATE DEFAULT NULL,
  start_time TIME DEFAULT NULL,
  end_time TIME DEFAULT NULL,
  operator VARCHAR(100) DEFAULT NULL,
  core_color VARCHAR(50) DEFAULT NULL,
  cam VARCHAR(50) DEFAULT NULL,
  tube VARCHAR(50) DEFAULT NULL,
  water_blocking_tape VARCHAR(50) DEFAULT NULL,
  fpr VARCHAR(50) DEFAULT NULL,
  kcs VARCHAR(50) DEFAULT NULL,
  water_blocking_yarn VARCHAR(50) DEFAULT NULL,
  binder VARCHAR(50) DEFAULT NULL,
  -- Thông số kỹ thuật BCT/CCT/FRP (khớp phiếu "LỆNH SẢN XUẤT LÕI SZ")
  fpr_type VARCHAR(50) DEFAULT NULL,   -- Chủng loại FPR, vd: 1*1500Dtex
  fpr_lot VARCHAR(50) DEFAULT NULL,    -- Lô số FPR
  binder_type VARCHAR(50) DEFAULT NULL, -- Chủng loại chỉ bện, vd: 2*2000Dtex
  binder_lot VARCHAR(50) DEFAULT NULL,  -- Lô số chỉ bện
  spec_summary VARCHAR(255) DEFAULT NULL, -- Ghi chú tổng, vd: "DB 24C, 5 P.TỬ, FRP 1.7mm"
  notes TEXT DEFAULT NULL,
  status VARCHAR(50) DEFAULT NULL,
  CONSTRAINT fk_plan_sz_roll FOREIGN KEY (roll_id) REFERENCES cable_rolls(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS plan_jacket (
  id INT AUTO_INCREMENT PRIMARY KEY,
  roll_id INT NOT NULL,
  operation_date DATE DEFAULT NULL,
  start_time TIME DEFAULT NULL,
  end_time TIME DEFAULT NULL,
  operator VARCHAR(100) DEFAULT NULL,
  roll_code VARCHAR(50) DEFAULT NULL,
  length FLOAT DEFAULT NULL,
  thickness FLOAT DEFAULT NULL,       -- Độ dày vỏ (mm)
  armor VARCHAR(100) DEFAULT NULL,
  cap VARCHAR(100) DEFAULT NULL,
  color VARCHAR(50) DEFAULT NULL,
  ripcord_count INT DEFAULT NULL,     -- Chỉ xé cáp
  hanging_steel VARCHAR(50) DEFAULT NULL, -- Thép treo, vd: 7x1.0mm
  notes TEXT DEFAULT NULL,
  status VARCHAR(50) DEFAULT NULL,
  CONSTRAINT fk_plan_jacket_roll FOREIGN KEY (roll_id) REFERENCES cable_rolls(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS production_info_loose_tube (
  id INT AUTO_INCREMENT PRIMARY KEY,
  roll_id INT NOT NULL,
  stt INT DEFAULT NULL,
  fiber_code VARCHAR(100) DEFAULT NULL,
  shift VARCHAR(50) DEFAULT NULL,
  tube_code VARCHAR(100) DEFAULT NULL,
  machine_speed FLOAT DEFAULT NULL,
  color VARCHAR(50) DEFAULT NULL,
  fiber_count INT DEFAULT NULL,
  diameter FLOAT DEFAULT NULL,
  length FLOAT DEFAULT NULL,          -- Chiều dài (m), vd: 24400 / 12200
  production_date DATE DEFAULT NULL,  -- Ngày sản xuất
  bobbin_count INT DEFAULT NULL,
  operator INT DEFAULT NULL,
  notes TEXT DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_prod_lt_roll FOREIGN KEY (roll_id) REFERENCES cable_rolls(id),
  CONSTRAINT fk_prod_lt_user FOREIGN KEY (operator) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS production_info_sz (
  id INT AUTO_INCREMENT PRIMARY KEY,
  roll_id INT NOT NULL,
  stt INT DEFAULT NULL,
  core_code VARCHAR(100) DEFAULT NULL,   -- Mã số sản phẩm, vd: SZ-25-59-01
  length FLOAT DEFAULT NULL,             -- Chiều dài
  tube_duong VARCHAR(100) DEFAULT NULL,  -- Mã ống lỏng màu Dương
  tube_cam VARCHAR(100) DEFAULT NULL,    -- Mã ống lỏng màu Cam
  tube_luc VARCHAR(100) DEFAULT NULL,    -- Mã ống lỏng màu Lục
  tube_nau VARCHAR(100) DEFAULT NULL,    -- Mã ống lỏng màu Nâu
  filler VARCHAR(50) DEFAULT NULL,
  production_date DATE DEFAULT NULL,
  operator INT DEFAULT NULL,
  notes TEXT DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_prod_sz_roll FOREIGN KEY (roll_id) REFERENCES cable_rolls(id),
  CONSTRAINT fk_prod_sz_user FOREIGN KEY (operator) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS production_info_jacket (
  id INT AUTO_INCREMENT PRIMARY KEY,
  roll_id INT NOT NULL,
  stt INT DEFAULT NULL,
  cable_code VARCHAR(100) DEFAULT NULL,    -- Mã cuộn cáp, vd: 25-58-01
  core_code VARCHAR(100) DEFAULT NULL,     -- Mã lõi dùng để bọc, vd: SZ-25-58-01
  product_label VARCHAR(255) DEFAULT NULL, -- Nhãn in trên vỏ, vd: "CVC VTVCAB DB 12FO 2025"
  length FLOAT DEFAULT NULL,               -- Chiều dài (km), vd: 3.002
  product_code VARCHAR(100) DEFAULT NULL,
  error_roll_code VARCHAR(100) DEFAULT NULL,
  product_type VARCHAR(100) DEFAULT NULL,
  manufacture_date DATE DEFAULT NULL,
  operator INT DEFAULT NULL,
  bl1 VARCHAR(50) DEFAULT NULL,
  head_length FLOAT DEFAULT NULL,
  tail_length FLOAT DEFAULT NULL,
  notes TEXT DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_prod_jacket_roll FOREIGN KEY (roll_id) REFERENCES cable_rolls(id),
  CONSTRAINT fk_prod_jacket_user FOREIGN KEY (operator) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS production_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  roll_id INT NOT NULL,
  stage VARCHAR(50) DEFAULT NULL,
  status VARCHAR(50) DEFAULT NULL,
  updated_by INT DEFAULT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  notes TEXT DEFAULT NULL,
  CONSTRAINT fk_logs_roll FOREIGN KEY (roll_id) REFERENCES cable_rolls(id),
  CONSTRAINT fk_logs_user FOREIGN KEY (updated_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qc_reports (
  id INT AUTO_INCREMENT PRIMARY KEY,
  roll_id INT NOT NULL,
  product_code VARCHAR(100) DEFAULT NULL,
  product_type VARCHAR(100) DEFAULT NULL,
  production_length FLOAT DEFAULT NULL,
  manufacture_date DATE DEFAULT NULL,
  shift VARCHAR(50) DEFAULT NULL,
  quality_rating VARCHAR(50) DEFAULT NULL,
  short_fiber INT DEFAULT NULL,
  broken_fiber INT DEFAULT NULL,
  checked_date DATETIME DEFAULT NULL,
  checked_by INT DEFAULT NULL,
  notes TEXT DEFAULT NULL,
  CONSTRAINT fk_qc_roll FOREIGN KEY (roll_id) REFERENCES cable_rolls(id),
  CONSTRAINT fk_qc_user FOREIGN KEY (checked_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =====================================================================
-- NHẬT KÝ THAO TÁC (AUDIT LOG) — ghi lại hành động của MỌI role
-- (đăng nhập, đổi mật khẩu, nhận việc/cập nhật trạng thái, tạo/xóa tài khoản...)
-- Lưu trực tiếp username + role tại thời điểm thao tác (denormalized) để
-- lịch sử không bị mất nếu tài khoản đó sau này bị xóa.
-- =====================================================================
CREATE TABLE IF NOT EXISTS audit_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) DEFAULT NULL,
  role VARCHAR(50) DEFAULT NULL,
  action VARCHAR(50) NOT NULL,        -- LOGIN | CHANGE_PASSWORD | UPDATE_ROLL_STATUS | CREATE_USER | DELETE_USER
  target VARCHAR(100) DEFAULT NULL,   -- vd: mã lô, username bị thao tác...
  description VARCHAR(255) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
