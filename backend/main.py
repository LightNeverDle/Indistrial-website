import os
import sys
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


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


class SubmitQcModel(BaseModel):
    product_code: str
    product_type: str
    production_length: Optional[float] = None
    manufacture_date: Optional[str] = None
    shift: Optional[str] = None
    quality_rating: str
    short_fiber: Optional[int] = None
    broken_fiber: Optional[int] = None
    checked_date: Optional[str] = None
    notes: Optional[str] = None


class LooseTubeFormModel(BaseModel):
    stt: Optional[int] = None
    fiber_code: Optional[str] = None
    shift: Optional[str] = None
    tube_code: Optional[str] = None
    machine_speed: Optional[float] = None
    color: Optional[str] = None
    fiber_count: Optional[int] = None
    diameter: Optional[float] = None
    length: Optional[float] = None
    production_date: Optional[str] = None
    bobbin_count: Optional[int] = None
    notes: Optional[str] = None


class SzFormModel(BaseModel):
    stt: Optional[int] = None
    product_code: Optional[str] = None
    core_code: Optional[str] = None
    shift: Optional[str] = None
    production_date: Optional[str] = None
    machine: Optional[str] = None
    machine_speed: Optional[float] = None
    length: Optional[float] = None
    sz_pitch: Optional[str] = None
    lay_direction: Optional[str] = None
    tension: Optional[str] = None
    pull_speed: Optional[float] = None
    post_braid_diameter: Optional[float] = None
    kcs_diameter: Optional[float] = None
    kcs_uniformity: Optional[str] = None
    kcs_external_inspection: Optional[str] = None
    kcs_notes: Optional[str] = None
    notes: Optional[str] = None


class JacketFormModel(BaseModel):
    stt: Optional[int] = None
    cable_code: Optional[str] = None
    core_code: Optional[str] = None
    product_label: Optional[str] = None
    product_type: Optional[str] = None
    shift: Optional[str] = None
    manufacture_date: Optional[str] = None
    bin: Optional[str] = None
    frp: Optional[str] = None
    bl1: Optional[str] = None
    head_length: Optional[float] = None
    tail_length: Optional[float] = None
    kcs_measurements: Optional[dict] = None
    measured_length: Optional[float] = None
    loss_result: Optional[str] = None
    measured_by: Optional[str] = None
    notes: Optional[str] = None


class JacketKcsFormModel(BaseModel):
    stt: Optional[int] = None
    cable_code: Optional[str] = None
    core_code: Optional[str] = None
    product_label: Optional[str] = None
    length: Optional[float] = None
    product_type: Optional[str] = None
    error_roll_code: Optional[str] = None
    manufacture_date: Optional[str] = None
    inspection_result: Optional[str] = None
    inspection_notes: Optional[str] = None
    notes: Optional[str] = None


# ==========================
# JWT
# ==========================

security = HTTPBearer()

def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập đã hết hạn!")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ!")


def verify_admin_token(
    payload=Depends(verify_token)
):
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Bị từ chối: Bạn không có quyền quản trị!"
        )

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
def change_password(
    data: ChangePasswordModel,
    payload=Depends(verify_token)
):
    username = payload["sub"]
    user = db.get_user(username)

    if not user:
        raise HTTPException(404, "Không tìm thấy tài khoản.")

    if not pwd_context.verify(data.old_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Mật khẩu cũ không đúng.")

    db.change_password(username, pwd_context.hash(data.new_password))
    db.add_audit_log(
        username,
        payload.get("role"),
        "CHANGE_PASSWORD",
        description="Tự đổi mật khẩu"
    )

    return {"message": "Đổi mật khẩu thành công."}


# ==========================
# CABLE ROLLS — DANH SÁCH THEO TAB
# ==========================

@app.get("/api/rolls")
def get_rolls(tab: str = "pending",payload=Depends(verify_token)):
    if tab not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Tab không hợp lệ.")

    return db.get_rolls(tab, payload["role"], payload["sub"])


# ==========================
# CABLE ROLLS — CHI TIẾT PHIẾU LỆNH
# ==========================

@app.get("/api/rolls/{roll_id}/detail")
def get_roll_detail(roll_id: int, payload=Depends(verify_token)):
    detail = db.get_roll_detail(roll_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy lô sản phẩm.")

    return detail


# ==========================
# CABLE ROLLS — CẬP NHẬT TRẠNG THÁI
# ==========================

@app.post("/api/rolls/{roll_id}/status")
def update_roll_status(roll_id: int, data: UpdateRollStatusModel, payload=Depends(verify_token)):
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


@app.post("/api/rolls/{roll_id}/qc")
def submit_qc_report(roll_id: int, data: SubmitQcModel, payload=Depends(verify_token)):
    if payload.get("role") not in {"admin", "inspector"}:
        raise HTTPException(status_code=403, detail="Bạn không có quyền thực hiện QC.")

    if data.quality_rating not in {"Đạt", "Không đạt"}:
        raise HTTPException(status_code=400, detail="Đánh giá chất lượng không hợp lệ.")

    payload_data = data.dict() if hasattr(data, "dict") else data.model_dump()
    ok = db.submit_qc_report(roll_id, payload_data, payload["sub"])
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy lô sản phẩm.")

    db.add_audit_log(
        payload["sub"], payload.get("role"), "QC_REPORT",
        target=f"roll#{roll_id}", description=f"Ghi nhận kết quả QC: {data.quality_rating}"
    )

    return {"status": "success", "message": "Đã lưu kết quả QC thành công."}


@app.post("/api/rolls/{roll_id}/loose-tube-form")
def submit_loose_tube_form(roll_id: int, data: LooseTubeFormModel, payload=Depends(verify_token)):
    if payload.get("role") not in {"worker1", "worker2", "worker3", "admin"}:
        raise HTTPException(status_code=403, detail="Bạn không có quyền nhập phiếu.")

    payload_data = data.dict() if hasattr(data, "dict") else data.model_dump()
    ok = db.create_loose_tube_form(roll_id, payload_data, payload["sub"])
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy lô sản phẩm hoặc không phải ống lỏng.")

    db.add_audit_log(
        payload["sub"], payload.get("role"), "SUBMIT_LOOSE_TUBE_FORM",
        target=f"roll#{roll_id}", description="Nhập phiếu thông tin ống lỏng"
    )

    return {"status": "success", "message": "Đã lưu phiếu thông tin ống lỏng."}


@app.post("/api/rolls/{roll_id}/sz-form")
def submit_sz_form(roll_id: int, data: SzFormModel, payload=Depends(verify_token)):
    if payload.get("role") not in {"worker1", "worker2", "worker3", "admin"}:
        raise HTTPException(status_code=403, detail="Bạn không có quyền nhập phiếu.")

    payload_data = data.dict() if hasattr(data, "dict") else data.model_dump()
    ok = db.create_sz_form(roll_id, payload_data, payload["sub"])
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy lô sản phẩm hoặc không phải Bện SZ.")

    db.add_audit_log(
        payload["sub"], payload.get("role"), "SUBMIT_SZ_FORM",
        target=f"roll#{roll_id}", description="Nhập phiếu thông tin Bện SZ"
    )

    return {"status": "success", "message": "Đã lưu phiếu thông tin Bện SZ."}


@app.post("/api/rolls/{roll_id}/jacket-form")
def submit_jacket_form(roll_id: int, data: JacketFormModel, payload=Depends(verify_token)):
    if payload.get("role") not in {"worker1", "worker2", "worker3", "admin"}:
        raise HTTPException(status_code=403, detail="Bạn không có quyền nhập phiếu.")

    payload_data = data.dict() if hasattr(data, "dict") else data.model_dump()
    ok = db.create_jacket_form(roll_id, payload_data, payload["sub"])
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy lô sản phẩm hoặc không phải Bọc vỏ." )

    db.add_audit_log(
        payload["sub"], payload.get("role"), "SUBMIT_JACKET_FORM",
        target=f"roll#{roll_id}", description="Nhập phiếu thông tin Bọc vỏ"
    )

    return {"status": "success", "message": "Đã lưu phiếu thông tin Bọc vỏ."}


@app.post("/api/rolls/{roll_id}/jacket-kcs-form")
def submit_jacket_kcs_form(roll_id: int, data: JacketKcsFormModel, payload=Depends(verify_token)):
    if payload.get("role") not in {"worker1", "worker2", "worker3", "admin"}:
        raise HTTPException(status_code=403, detail="Bạn không có quyền nhập phiếu.")

    payload_data = data.dict() if hasattr(data, "dict") else data.model_dump()
    ok = db.create_jacket_kcs_form(roll_id, payload_data, payload["sub"])
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy lô sản phẩm hoặc không phải Bọc vỏ KCS." )

    db.add_audit_log(
        payload["sub"], payload.get("role"), "SUBMIT_JACKET_KCS_FORM",
        target=f"roll#{roll_id}", description="Nhập phiếu thông tin KCS Bọc vỏ"
    )

    return {"status": "success", "message": "Đã lưu phiếu thông tin KCS Bọc vỏ."}


@app.get("/api/loose-tube-forms")
def get_loose_tube_forms(
    roll_code: Optional[str] = None,
    contract_code: Optional[str] = None,
    worker: Optional[str] = None,
    production_date: Optional[str] = None,
    shift: Optional[str] = None,
    payload=Depends(verify_admin_token)
):
    return db.get_loose_tube_forms(roll_code, contract_code, worker, production_date, shift)


@app.get("/api/loose-tube-forms/{form_id}")
def get_loose_tube_form_detail(form_id: int, payload=Depends(verify_admin_token)):
    form = db.get_loose_tube_form_by_id(form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu thông tin ống lỏng.")
    for k, v in form.items():
        if hasattr(v, "isoformat"):
            form[k] = str(v)
    return form


@app.get("/api/sz-forms")
def get_sz_forms(
    roll_code: Optional[str] = None,
    contract_code: Optional[str] = None,
    worker: Optional[str] = None,
    production_date: Optional[str] = None,
    shift: Optional[str] = None,
    payload=Depends(verify_admin_token)
):
    return db.get_sz_forms(roll_code, contract_code, worker, production_date, shift)


@app.get("/api/sz-forms/{form_id}")
def get_sz_form_detail(form_id: int, payload=Depends(verify_admin_token)):
    form = db.get_sz_form_by_id(form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu Bện SZ.")
    for k, v in form.items():
        if hasattr(v, "isoformat"):
            form[k] = str(v)
    return form


@app.get("/api/jacket-forms")
def get_jacket_forms(
    roll_code: Optional[str] = None,
    contract_code: Optional[str] = None,
    worker: Optional[str] = None,
    production_date: Optional[str] = None,
    shift: Optional[str] = None,
    payload=Depends(verify_admin_token)
):
    return db.get_jacket_forms(roll_code, contract_code, worker, production_date, shift)


@app.get("/api/jacket-forms/{form_id}")
def get_jacket_form_detail(form_id: int, payload=Depends(verify_admin_token)):
    form = db.get_jacket_form_by_id(form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu Bọc vỏ.")
    for k, v in form.items():
        if hasattr(v, "isoformat"):
            form[k] = str(v)
    return form


@app.get("/api/jacket-kcs-forms")
def get_jacket_kcs_forms(
    roll_code: Optional[str] = None,
    contract_code: Optional[str] = None,
    worker: Optional[str] = None,
    production_date: Optional[str] = None,
    shift: Optional[str] = None,
    payload=Depends(verify_admin_token)
):
    return db.get_jacket_kcs_forms(roll_code, contract_code, worker, production_date, shift)


@app.get("/api/jacket-kcs-forms/{form_id}")
def get_jacket_kcs_form_detail(form_id: int, payload=Depends(verify_admin_token)):
    form = db.get_jacket_kcs_form_by_id(form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu KCS Bọc vỏ.")
    for k, v in form.items():
        if hasattr(v, "isoformat"):
            form[k] = str(v)
    return form


# ==========================
# USERS (Admin)
# ==========================

@app.get("/api/users")
def get_all_users(
    payload = Depends(verify_admin_token)
):
    return db.get_users()


@app.post("/api/users")
def create_user(data: CreateUserModel, payload=Depends(verify_admin_token)):
    if db.get_user(data.username):
        raise HTTPException(status_code=400, detail="Tài khoản đã tồn tại.")

    db.create_user(data.username, pwd_context.hash(data.password), data.role)
    db.add_audit_log(
        payload["sub"], "admin", "CREATE_USER",
        target=data.username, description=f"Tạo tài khoản mới với vai trò '{data.role}'"
    )
    return {"message": f"Đã tạo tài khoản {data.username} thành công."}


@app.delete("/api/users/{username}")
def delete_user(username: str, payload=Depends(verify_admin_token)):
    if username == "admin":
        raise HTTPException(status_code=403, detail="Không thể xóa tài khoản admin.")

    db.delete_user(username)
    db.add_audit_log(payload["sub"], "admin", "DELETE_USER", target=username, description="Xóa tài khoản")
    return {"message": f"Đã xóa tài khoản {username}."}


# ==========================
# NHẬT KÝ THAO TÁC (AUDIT LOG) — chỉ admin được xem
# ==========================

@app.get("/api/audit-logs")
def get_audit_logs(role: str = "all", payload=Depends(verify_admin_token)):
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
