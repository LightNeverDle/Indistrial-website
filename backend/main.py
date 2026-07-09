import os
import sys
from datetime import datetime, timedelta

import jwt
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ==========================
# Chuyển thư mục làm việc về Project/
# ==========================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

os.chdir(PROJECT_ROOT)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import db, pwd_context, NEXT_STATUS  # noqa: E402

app = FastAPI(title="Secure Factory OS v4.0 (MySQL)")

SECRET_KEY = "FACTORY_PRO_MAX"
ALGORITHM = "HS256"

VALID_STATUSES = {"pending", "processing", "pending-inspect", "rejected", "completed"}


# ==========================
# Pydantic Models
# ==========================

class LoginModel(BaseModel):
    username: str
    password: str


class ChangePasswordModel(BaseModel):
    old_password: str
    new_password: str


class UpdateRollStatusModel(BaseModel):
    status: str


class CreateUserModel(BaseModel):
    username: str
    password: str
    role: str


# ==========================
# JWT
# ==========================

def verify_token(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập lại!")

    token = authorization.split(" ")[1]

    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn!")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ!")


def verify_admin_token(authorization: str):
    payload = verify_token(authorization)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Bị từ chối: Bạn không có quyền quản trị!")
    return payload


# ==========================
# LOGIN / ĐỔI MẬT KHẨU
# ==========================

@app.post("/api/login")
def login(data: LoginModel):
    user = db.get_user(data.username)

    if not user or not pwd_context.verify(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Sai tài khoản hoặc mật khẩu!")

    token_data = {
        "sub": data.username,
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(hours=2),
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

    db.add_audit_log(data.username, user["role"], "LOGIN", description="Đăng nhập hệ thống")

    return {
        "status": "success",
        "token": token,
        "username": data.username,
        "role": user["role"],
    }


@app.post("/api/change-password")
def change_password(data: ChangePasswordModel, authorization: str = Header(None)):
    payload = verify_token(authorization)
    username = payload["sub"]
    user = db.get_user(username)

    if not user:
        raise HTTPException(404, "Không tìm thấy tài khoản.")

    if not pwd_context.verify(data.old_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không đúng.")

    db.change_password(username, pwd_context.hash(data.new_password))
    db.add_audit_log(username, payload.get("role"), "CHANGE_PASSWORD", description="Tự đổi mật khẩu")

    return {"message": "Đổi mật khẩu thành công."}


# ==========================
# CABLE ROLLS — DANH SÁCH THEO TAB
# ==========================

@app.get("/api/rolls")
def get_rolls(tab: str = "pending", authorization: str = Header(None)):
    payload = verify_token(authorization)

    if tab not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Tab không hợp lệ.")

    return db.get_rolls(tab, payload["role"], payload["sub"])


# ==========================
# CABLE ROLLS — CHI TIẾT PHIẾU LỆNH
# ==========================

@app.get("/api/rolls/{roll_id}/detail")
def get_roll_detail(roll_id: int, authorization: str = Header(None)):
    verify_token(authorization)

    detail = db.get_roll_detail(roll_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy lô sản phẩm.")

    return detail


# ==========================
# CABLE ROLLS — CẬP NHẬT TRẠNG THÁI
# ==========================

@app.post("/api/rolls/{roll_id}/status")
def update_roll_status(roll_id: int, data: UpdateRollStatusModel, authorization: str = Header(None)):
    payload = verify_token(authorization)
    username = payload["sub"]

    if data.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Trạng thái không hợp lệ.")

    roll = db.get_roll_status(roll_id)
    if not roll:
        raise HTTPException(status_code=404, detail="Không tìm thấy lô sản phẩm.")

    ok = db.update_roll_status(roll_id, data.status, username)
    if not ok:
        raise HTTPException(status_code=400, detail="Cập nhật thất bại.")

    db.add_audit_log(
        username, payload.get("role"), "UPDATE_ROLL_STATUS",
        target=f"roll#{roll_id}", description=f"Cập nhật trạng thái sang '{data.status}'"
    )

    return {"status": "success", "message": f"Đã cập nhật trạng thái: {data.status}"}


# ==========================
# USERS (Admin)
# ==========================

@app.get("/api/users")
def get_all_users(authorization: str = Header(None)):
    verify_admin_token(authorization)
    return db.get_users()


@app.post("/api/users")
def create_user(data: CreateUserModel, authorization: str = Header(None)):
    payload = verify_admin_token(authorization)

    if db.get_user(data.username):
        raise HTTPException(status_code=400, detail="Tài khoản đã tồn tại.")

    db.create_user(data.username, pwd_context.hash(data.password), data.role)
    db.add_audit_log(
        payload["sub"], "admin", "CREATE_USER",
        target=data.username, description=f"Tạo tài khoản mới với vai trò '{data.role}'"
    )
    return {"message": f"Đã tạo tài khoản {data.username} thành công."}


@app.delete("/api/users/{username}")
def delete_user(username: str, authorization: str = Header(None)):
    payload = verify_admin_token(authorization)

    if username == "admin":
        raise HTTPException(status_code=403, detail="Không thể xóa tài khoản admin.")

    db.delete_user(username)
    db.add_audit_log(payload["sub"], "admin", "DELETE_USER", target=username, description="Xóa tài khoản")
    return {"message": f"Đã xóa tài khoản {username}."}


# ==========================
# NHẬT KÝ THAO TÁC (AUDIT LOG) — chỉ admin được xem
# ==========================

@app.get("/api/audit-logs")
def get_audit_logs(role: str = "all", authorization: str = Header(None)):
    verify_admin_token(authorization)
    return db.get_audit_logs(role=role)


# ==========================
# FRONTEND
# ==========================

@app.get("/")
def read_index():
    return FileResponse("frontend/index.html")


app.mount("/", StaticFiles(directory="frontend"), name="frontend")


# ==========================
# RUN SERVER
# ==========================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
