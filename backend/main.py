import os
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sqlite3
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta

app = FastAPI(title="Secure Factory OS v4.0")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DB_PATH = "backend/factory.db"

SECRET_KEY = "FACTORY_PRO_MAX"
ALGORITHM = "HS256"

def init_db():
    os.makedirs("backend", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Khởi tạo bảng users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, password_hash TEXT, role TEXT
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ("admin", pwd_context.hash("123456"), "admin"),
            ("worker1", pwd_context.hash("123456"), "worker1"),
            ("worker2", pwd_context.hash("123456"), "worker2")
        ]
        cursor.executemany("INSERT INTO users VALUES (?, ?, ?)", default_users)
    
    # 2. Khởi tạo bảng loose_tube_orders (Dữ liệu thật)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loose_tube_orders (
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
    ''')
    
    # Tạo mockdata dữ liệu thật chưa xử lý nếu bảng trống
    cursor.execute("SELECT COUNT(*) FROM loose_tube_orders")
    if cursor.fetchone()[0] == 0:
        mock_orders = [
            ("Công ty Cáp Quang Việt Nam", "HD-2026-001", "2026-06-25","Trần Văn A", "Quản đốc Nguyễn Văn A", 
             "OL-D2.5-08", "2026-06-25", "08:00", "12:00", "worker1", "Xanh dương", 8, 2.5, 2000.0, 
             "Yêu cầu kiểm tra kỹ độ căng sợi", "Chưa xử lý"),
            ("Tập đoàn Viễn thông Á Châu", "HD-2026-002", "2026-06-25","Trần Văn A", "Quản đốc Nguyễn Văn A", 
             "OL-D3.0-24", "2026-06-25", "13:30", "17:30", "worker1", "Màu vàng", 24, 3.0, 1500.0, 
             "Đóng gói bằng rulo gỗ bọc màng PE", "Chưa xử lý"),
            ("Bưu điện Thành phố", "HD-2026-003", "2026-06-25","Trần Văn A", "Trưởng ca Lê Văn B", 
             "OL-D2.0-04", "2026-06-26", "07:30", "11:30", "worker1", "Màu đỏ", 4, 2.0, 3500.0, 
             "Giao hàng trước 4h chiều", "Chưa xử lý")
        ]
        cursor.executemany('''
            INSERT INTO loose_tube_orders (
                customer_name, contract_code, import_date, requester, approver, loose_tube_code, 
                operation_date, start_time, end_time, operator, tube_color, 
                fiber_count, diameter, length, notes, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', mock_orders)
        
    conn.commit()
    conn.close()

init_db()

class LoginModel(BaseModel):
    username: str
    password: str

class UpdateStatusModel(BaseModel):
    order_id: int
    status: str

# Giải mã token chung
def verify_token(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập lại!")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn!")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ!")

# Kiểm tra quyền riêng cho admin khi tương tác quản trị user
def verify_admin_token(authorization: str):
    payload = verify_token(authorization)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Bị từ chối: Bạn không có quyền quản trị!")
    return payload

@app.post("/api/login")
def login(data: LoginModel):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash, role FROM users WHERE username = ?", (data.username,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not pwd_context.verify(data.password, user[0]):
        raise HTTPException(status_code=401, detail="Sai tài khoản hoặc mật khẩu!")
    
    token_data = {
        "sub": data.username,
        "role": user[1],
        "exp": datetime.utcnow() + timedelta(hours=2)
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    return {"status": "success", "token": token, "username": data.username, "role": user[1]}

# API lấy danh sách Phiếu lệnh (Chỉ chưa xử lý, Chỉ cho admin và worker1 thấy)
@app.get("/api/my-orders")
def get_my_orders(authorization: str = Header(None)):
    payload = verify_token(authorization)
    current_user = payload.get("sub")
    current_role = payload.get("role")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Logic phân quyền:
    # Admin: Thấy tất cả. Worker1: Thấy bảng loose_tube_orders.
    # Các worker khác: Tương lai sẽ thêm table riêng tại đây.
    if current_role == "admin":
        cursor.execute("SELECT * FROM loose_tube_orders")
    elif current_user == "worker1":
        cursor.execute("SELECT * FROM loose_tube_orders WHERE status = 'Chưa xử lý'")
    else:
        # Nếu là worker khác, trả về danh sách rỗng hoặc logic mở rộng sau này
        cursor.execute("SELECT * FROM loose_tube_orders WHERE 1=0") 
        
    orders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return orders

# API Cập nhật trạng thái phiếu lệnh
@app.post("/api/update-order-status")
def update_order_status(data: UpdateStatusModel, authorization: str = Header(None)):
    payload = verify_token(authorization)
    current_user = payload.get("sub")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Kiểm tra xem phiếu có tồn tại và ai là người vận hành máy được chỉ định
    cursor.execute("SELECT operator, status FROM loose_tube_orders WHERE id = ?", (data.order_id,))
    order = cursor.fetchone()
    
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu lệnh này!")
        
    if order[0] != current_user:
        conn.close()
        raise HTTPException(status_code=403, detail=f"Bị từ chối: Phiếu này được chỉ định cho [{order[0]}], bạn là [{current_user}] không được bấm nhận!")

    cursor.execute("UPDATE loose_tube_orders SET status = ? WHERE id = ?", (data.status, data.order_id))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Đã cập nhật trạng thái lệnh sản xuất thành công!"}

# Giữ nguyên các API cũ bên dưới...
@app.get("/api/users")
def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username, role FROM users")
    users = [{"username": row[0], "role": row[1]} for row in cursor.fetchall()]
    conn.close()
    return users

@app.get("/")
def read_index(): return FileResponse("frontend/index.html")
app.mount("/", StaticFiles(directory="frontend"), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)