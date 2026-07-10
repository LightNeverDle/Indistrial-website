# Smart Factory Website

Đây là một ứng dụng web quản lý sản xuất sử dụng FastAPI cho backend, MySQL cho cơ sở dữ liệu và HTML/CSS/JavaScript cho frontend.

## 1. Ứng dụng hoạt động như thế nào?

Web này cho phép người dùng:
- đăng nhập vào hệ thống bằng tài khoản và mật khẩu
- xem danh sách công việc theo từng trạng thái: chờ xử lý, đang xử lý, chờ kiểm định, bị từ chối
- xem chi tiết từng phiếu lệnh sản xuất
- cập nhật trạng thái công việc
- quản lý tài khoản (nếu là admin)
- xem nhật ký thao tác hệ thống (nếu là admin)

## 2. Công nghệ sử dụng

- Backend: FastAPI
- Database: MySQL
- Frontend: HTML, CSS, JavaScript
- Xác thực: JWT
- Mã hóa mật khẩu: bcrypt

## 3. Yêu cầu hệ thống

Trước khi chạy, cần chuẩn bị:
- Python 3.9+ (khuyến nghị 3.10+)
- MySQL Server đang chạy
- Git (nếu cần clone project)

## 4. Cài đặt

### Bước 1: Vào thư mục backend

```bash
cd backend
```

### Bước 2: Cài đặt thư viện Python

```bash
pip install -r requirements.txt
```

### Bước 3: Cấu hình kết nối MySQL

Ứng dụng sẽ đọc các biến môi trường sau:

- DB_HOST
- DB_PORT
- DB_USER
- DB_PASSWORD
- DB_NAME

Nếu không khai báo, hệ thống sẽ dùng giá trị mặc định:
- host: 127.0.0.1
- port: 3306
- user: root
- password: rỗng
- database: factory_management

Ví dụ trên Windows PowerShell:

```powershell
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
$env:DB_USER="root"
$env:DB_PASSWORD=""
$env:DB_NAME="factory_management"
```

Ví dụ trên bash/Linux/macOS:

```bash
export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=""
export DB_NAME=factory_management
```

> Nếu database chưa tồn tại, hệ thống sẽ tự tạo database và bảng khi khởi động.

## 5. Chạy ứng dụng

### Chạy backend

Từ thư mục backend:

```bash
python main.py
```

Hoặc dùng uvicorn:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Mở trình duyệt

Sau khi backend chạy, mở địa chỉ:

```text
http://127.0.0.1:8000/
```

## 6. Tài khoản mặc định

Khi database khởi tạo lần đầu, hệ thống sẽ tự tạo dữ liệu mẫu, bao gồm các tài khoản sau:

- admin / 123456
- worker1 / 123456
- worker2 / 123456
- inspector / 123456

## 7. Một số chức năng chính

- Đăng nhập và đăng xuất
- Xem công việc theo từng tab trạng thái
- Nhận việc / chuyển trạng thái công việc
- Xem chi tiết phiếu lệnh sản xuất
- Quản lý tài khoản và xem nhật ký thao tác (admin)

## 8. Lưu ý

- Nếu bạn đổi mật khẩu, cần đăng nhập lại để nhận token mới.
- Nếu có lỗi kết nối MySQL, hãy kiểm tra MySQL đang chạy và thông tin đăng nhập trong biến môi trường.
- Nếu muốn chạy ở môi trường khác, hãy cập nhật lại các biến DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.
