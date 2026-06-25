const API_URL = "http://127.0.0.1:8000/api";
let authToken = null; 
let currentUsername = null; // Lưu trữ username của người dùng đang đăng nhập

// Giữ nguyên mockdata của các mục khác
const mockTasks = {
    processing: [
        { id: 3, title: "Phiếu chuẩn bị vật tư sản xuất Ống Lỏng", desc: "Đang chạy trên máy CNC 01" }
    ],
    "pending-inspect": [
        { id: 4, title: "phiếu thông tin sản xuất Ống Lỏng", desc: "Chờ Inspector kiểm tra mạch điện" }
    ],
    rejected: [
        { id: 5, title: "QC", desc: "Đã ký duyệt đạt chuẩn" }
    ]
};

const loginScreen = document.getElementById("login-screen");
const dashboardScreen = document.getElementById("dashboard-screen");
const taskList = document.getElementById("task-list");
const adminPanel = document.getElementById("admin-panel");
const tabTitle = document.getElementById("tab-title");
const adminNav = document.getElementById("admin-nav");

// 1. LOGIC CHUYỂN TAB ĐIỀU HƯỚNG
document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", function() {
        document.querySelector(".nav-item.active").classList.remove("active");
        this.classList.add("active");
        const tab = this.getAttribute("data-tab");
        if (tab === "admin-panel") {
            tabTitle.textContent = "Quản lý cấp phát tài khoản";
            taskList.classList.add("hidden");
            adminPanel.classList.remove("hidden");
            loadUsers();
        } else {
            taskList.classList.remove("hidden");
            adminPanel.classList.add("hidden");
            
            if (tab === "pending") {
                renderRealOrders(); // DỮ LIỆU THẬT CHO TAB PENDING
            } else {
                renderTasks(tab);  // MOCK DATA CHO CÁC TAB KHÁC
            }
        }
    });
});

// Hàm hiển thị DỮ LIỆU THẬT từ SQLite cho tab "Công việc đang chờ"
async function renderRealOrders() {
    tabTitle.textContent = "Công việc của tôi";
    taskList.innerHTML = `<p style="grid-column:1/-1; text-align:center;">Đang tải dữ liệu...</p>`;
    
    try {
        const response = await fetch(`${API_URL}/my-orders`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${authToken}` }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            taskList.innerHTML = `<p style="color:var(--error); text-align:center;">${data.detail || "Lỗi quyền truy cập"}</p>`;
            return;
        }

        taskList.innerHTML = "";
        
        if (data.length === 0) {
            taskList.innerHTML = `<p style="grid-column:1/-1; text-align:center; color:var(--text-muted);">Không có công việc nào dành cho bạn.</p>`;
            return;
        }

        data.forEach(order => {
            const card = document.createElement("div");
            card.className = "task-card";
            
            // Nút hành động
            const buttonHtml = order.status === 'Chưa xử lý' 
                ? `<button class="btn btn-confirm" onclick="acceptOrder(${order.id})">✓ Nhận việc</button>` 
                : `<button class="btn btn-secondary" disabled>Đã nhận</button>`;

            // Hiển thị đầy đủ thông tin
            card.innerHTML = `
                <h3 style="color: var(--primary-neon);">Phiếu lệnh sản xuất Ống Lỏng</h3>
                <h3 style="color: var(--primary-neon);">#${order.id} - ${order.loose_tube_code}</h3>
                <hr style="border: 0; border-top: 1px solid var(--border-color); margin: 10px 0;">
                <div style="font-size: 0.85rem; display: grid; gap: 5px;">
                    <p><strong>Khách hàng:</strong> ${order.customer_name}</p>
                    <p><strong>Hợp đồng:</strong> ${order.contract_code}</p>
                    <p><strong>Ngày nhập:</strong> ${order.import_date}</p>
                    <p><strong>Thông số:</strong> ${order.fiber_count} sợi | ${order.diameter}mm | ${order.tube_color}</p>
                    <p><strong>Thời gian:</strong> ${order.start_time} - ${order.end_time}</p>
                    <p><strong>Người vận hành:</strong> ${order.operator}</p>
                    <p><strong>Ghi chú:</strong> ${order.notes || 'Không có'}</p>
                    <p><strong>Trạng thái:</strong> <span class="highlight">${order.status}</span></p>
                </div>
                <div style="margin-top: 15px;">
                    ${buttonHtml}
                </div>
            `;
            taskList.appendChild(card);
        });
    } catch (err) {
        taskList.innerHTML = `<p style="color:var(--error); text-align:center;">Không thể kết nối máy chủ.</p>`;
    }
}

// Hàm gửi xác nhận trạng thái về cho DB Backend
async function acceptOrder(orderId) {
    try {
        const response = await fetch(`${API_URL}/update-order-status`, {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify({ order_id: orderId, status: "Đang xử lý" })
        });
        const result = await response.json();
        if (response.ok) {
            alert("✓ " + result.message);
            renderRealOrders(); // Nạp lại danh sách sau khi lưu thành công
        } else {
            alert("❌ " + result.detail);
        }
    } catch (err) {
        alert("Lỗi đường truyền dữ liệu lên máy chủ.");
    }
}

// Hiển thị Mock Data cho các tab phụ còn lại
function renderTasks(status) {
    const titles = { 
        processing: "Công việc đang xử lý", 
        "pending-inspect": "Công việc đợi kiểm định", 
        rejected: "Công việc đã kiểm định" 
    };
    tabTitle.textContent = titles[status];
    taskList.innerHTML = "";
    
    if (mockTasks[status] && mockTasks[status].length > 0) {
        mockTasks[status].forEach(task => {
            const card = document.createElement("div");
            card.className = "task-card";
            if (status === "pending-inspect") card.style.borderTopColor = "#f59e0b";
            if (status === "rejected") card.style.borderTopColor = "#b92c10";
            card.innerHTML = `<h3>#${task.id} ${task.title}</h3><p>${task.desc}</p>`;
            taskList.appendChild(card);
        });
    } else {
        taskList.innerHTML = `<p style="grid-column:1/-1; text-align:center; color:var(--text-muted);">Không có công việc nào.</p>`;
    }
}

// ĐĂNG NHẬP để nhận token cùng định dạng danh tính người vận hành
document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const user = document.getElementById("username").value.trim();
    const pass = document.getElementById("password").value;
    const loginError = document.getElementById("login-error");
    loginError.textContent = "";

    try {
        const response = await fetch(`${API_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: user, password: pass })
        });
        const result = await response.json();

        if (response.ok) {
            authToken = result.token;
            currentUsername = result.username; // Lưu trữ phục vụ kiểm tra điều kiện nút bấm
            
            document.getElementById("user-display").textContent = result.username.toUpperCase();
            document.getElementById("role-display").textContent = result.role.toUpperCase();
            
            if (result.role === "admin") { adminNav.classList.remove("hidden"); } else { adminNav.classList.add("hidden"); }

            loginScreen.classList.add("hidden");
            dashboardScreen.classList.remove("hidden");
            
            renderRealOrders(); // Mặc định chạy dữ liệu thật ngay sau đăng nhập thành công
        } else { loginError.textContent = result.detail; }
    } catch (err) { loginError.textContent = "Không thể kết nối đến máy chủ."; }
});

// Giữ nguyên hàm loadUsers và deleteUser cũ của bạn...
async function loadUsers() {
    const tbody = document.getElementById("user-table-body");
    tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:var(--text-muted);">Đang tải dữ liệu...</td></tr>`;
    try {
        const response = await fetch(`${API_URL}/users`);
        const users = await response.json();
        tbody.innerHTML = "";
        users.forEach(user => {
            const tr = document.createElement("tr");
            const deleteButton = user.username === "admin" 
                ? `<span style="color:var(--text-muted); font-size:0.8rem;">Hệ thống bảo vệ</span>`
                : `<button class="btn-delete-task" onclick="deleteUser('${user.username}')">Xóa</button>`;
            tr.innerHTML = `<td><strong>${user.username}</strong></td><td><span class="highlight">${user.role.toUpperCase()}</span></td><td>${deleteButton}</td>`;
            tbody.appendChild(tr);
        });
    } catch (err) { tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:var(--error);">Lỗi tải dữ liệu.</td></tr>`; }
}

// Logic ĐĂNG XUẤT (Cập nhật để reset trạng thái an toàn)
document.getElementById("logout-btn").addEventListener("click", (e) => {
    e.preventDefault(); // Ngăn chặn các hành vi mặc định nếu nút nằm trong form
    
    // 1. Xóa sạch dữ liệu phiên đăng nhập hiện tại
    authToken = null;
    userRole = null;
    currentUsername = null;
    
    // 2. Reset toàn bộ form đăng nhập về trống
    const loginForm = document.getElementById("login-form");
    if (loginForm) loginForm.reset();
    
    // 3. Ẩn dashboard và hiển thị lại màn hình đăng nhập
    dashboardScreen.classList.add("hidden");
    loginScreen.classList.remove("hidden");
    
    // 4. Reset các thông tin hiển thị user trên thanh điều hướng
    document.getElementById("user-display").textContent = "";
    document.getElementById("role-display").textContent = "";
    if (adminNav) adminNav.classList.add("hidden");
    
    // 5. Làm mới lại trang để giải phóng bộ nhớ (Tùy chọn - An toàn hơn location.reload())
    window.location.href = window.location.pathname; 
});