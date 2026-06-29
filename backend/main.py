import os
import sys
import jwt
from datetime import datetime, timedelta
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
from backend.database import db, pwd_context

app = FastAPI(title="Secure Factory OS v4.0")

SECRET_KEY = "FACTORY_PRO_MAX"
ALGORITHM = "HS256"




# ==========================
# Pydantic Models
# ==========================

class LoginModel(BaseModel):
    username: str
    password: str

class ChangePasswordModel(BaseModel):
    old_password: str
    new_password: str

class UpdateStatusModel(BaseModel):
    contract_code:str
    status:str


# ==========================
# JWT
# ==========================

def verify_token(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Vui lòng đăng nhập lại!"
        )

    token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Phiên đăng nhập đã hết hạn!"
        )

    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Token không hợp lệ!"
        )


def verify_admin_token(authorization: str):
    payload = verify_token(authorization)

    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Bị từ chối: Bạn không có quyền quản trị!"
        )

    return payload


# ==========================
# LOGIN
# ==========================

@app.post("/api/change-password")
def change_password(
    data: ChangePasswordModel,
    authorization: str = Header(None)
):

    payload = verify_token(authorization)

    username = payload["sub"]

    user = db.get_user(username)

    if not user:
        raise HTTPException(404, "Không tìm thấy tài khoản.")

    if not pwd_context.verify(data.old_password, user["password_hash"]):
        raise HTTPException(
            status_code=400,
            detail="Mật khẩu cũ không đúng."
        )

    db.change_password(
        username,
        pwd_context.hash(data.new_password)
    )

    return {
        "message":"Đổi mật khẩu thành công."
    }

@app.post("/api/login")
def login(data: LoginModel):

    user = db.get_user(data.username)

    if not user or not pwd_context.verify(
        data.password,
        user["password_hash"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Sai tài khoản hoặc mật khẩu!"
        )

    token_data = {
        "sub": data.username,
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(hours=2)
    }

    token = jwt.encode(
        token_data,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return {
        "status": "success",
        "token": token,
        "username": data.username,
        "role": user["role"]
    }


# ==========================
# LẤY DANH SÁCH LỆNH
# ==========================

@app.get("/api/my-orders")
def get_my_orders(authorization: str = Header(None)):

    payload = verify_token(authorization)

    return db.get_orders(
        payload["role"],
        payload["sub"]
    )


# ==========================
# CẬP NHẬT TRẠNG THÁI
# ==========================

@app.post("/api/update-order-status")
def update_order_status(data:UpdateStatusModel,
                        authorization:str=Header(None)):

    payload=verify_token(authorization)

    current_user=payload["sub"]

    order=db.get_contract(data.contract_code)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy phiếu"
        )

    if order["operator"]!=current_user:
        raise HTTPException(
            status_code=403,
            detail="Bạn không được nhận phiếu này"
        )

    db.update_order_status(
        data.contract_code,
        data.status
    )

    return {
        "status":"success",
        "message":"Đã nhận phiếu thành công"
    }

# ==========================
# USERS
# ==========================

@app.get("/api/users")
def get_all_users():
    return db.get_users()


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

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )