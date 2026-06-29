const API_URL = "http://127.0.0.1:8000/api";
let authToken = null; 
let currentUsername = null; // Lưu trữ username của người dùng đang đăng nhập
let orderDetails = {};

// Giữ nguyên mockdata của các mục khác
const mockTasks = {
    processing: [
        { id: 3, title: "Phiếu chuẩn bị vật tư sản xuất Ống Lỏng", desc: "Đang chạy trên máy 01" }
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

// Trả về nút phù hợp theo trạng thái đơn
function renderStatusButton(group) {
    const status = group.status || group.state || group.order_status || "Chờ";
    const code = group.contract_code;

    if (status === "Hoàn thành" || status.toLowerCase() === "completed") {
        return `<button class="btn btn-complete btn-disabled" disabled>Hoàn thành</button>`;
    }

    if (status === "Đang xử lý" || status.toLowerCase() === "processing") {
        // Cho phép chuyển từ Đang xử lý -> Hoàn thành
        return `<button class="btn btn-processing" onclick='acceptOrder("${code}", "Đang xử lý")'>Đang xử lý → Hoàn thành</button>`;
    }

    // Mặc định: chưa nhận việc
    return `<button class="btn btn-confirm" onclick='acceptOrder("${code}", "${status}")'>Nhận việc</button>`;
}

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
        console.log(data);
        
        if (!response.ok) {
            taskList.innerHTML = `<p style="color:var(--error); text-align:center;">${data.detail || "Lỗi quyền truy cập"}</p>`;
            return;
        }

        taskList.innerHTML = "";
        
        if (data.length === 0) {
            taskList.innerHTML = `<p style="grid-column:1/-1; text-align:center; color:var(--text-muted);">Không có công việc nào dành cho bạn.</p>`;
            return;
        }

        data.forEach(group => {
            const card = document.createElement("div");
            card.className = "task-card";
            orderDetails[group.contract_code] = group.details;
            
            // Hiển thị đầy đủ thông tin
            card.innerHTML=`

            <h3 style="color:var(--primary-neon)">
            📋 ${group.contract_code}
            </h3>

            <hr>

            <p><b>Khách hàng:</b> ${group.customer_name}</p>

            <p><b>Người lập:</b> ${group.requester}</p>

            <p><b>Người duyệt:</b> ${group.approver}</p>

            <p><b>Người vận hành:</b> ${group.operator}</p>

            <p><b>Số sản phẩm:</b> ${group.product_count}</p>

            <p><b>Ngày nhập:</b> ${group.import_date}</p>

            <div style="margin-top:15px">

            <button
            class="btn btn-secondary"
            onclick="showOrderDetail('${group.contract_code}')">
            Chi tiết
            </button>

            <!-- Button hiển thị theo trạng thái -->
            ${renderStatusButton(group)}

            </div>

            `;
            taskList.appendChild(card);
        });
    } catch (err) {
        taskList.innerHTML = `<p style="color:var(--error); text-align:center;">Không thể kết nối máy chủ.</p>`;
    }
}

// Hàm gửi xác nhận trạng thái về cho DB Backend
async function acceptOrder(contractCode, currentStatus){
    // Xác định trạng thái tiếp theo
    let nextStatus = null;

    const cs = (currentStatus || "").toString();
    if (cs === "Hoàn thành" || cs.toLowerCase() === "completed") {
        alert("Đơn hàng đã hoàn thành.");
        return;
    }

    if (cs === "Đang xử lý" || cs.toLowerCase() === "processing") {
        nextStatus = "Hoàn thành";
    } else {
        // Mặc định chuyển sang Đang xử lý khi nhận việc
        nextStatus = "Đang xử lý";
    }

    try{
        const response = await fetch(`${API_URL}/update-order-status`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify({ contract_code: contractCode, status: nextStatus })
        });

        const result = await response.json();

        if (response.ok) {
            alert(result.message || `Cập nhật trạng thái: ${nextStatus}`);
            renderRealOrders();
        } else {
            alert(result.detail || "Cập nhật thất bại.");
        }
    } catch (e) {
        alert("Không thể kết nối server");
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

function showOrderDetail(contractCode) {

    const details = orderDetails[contractCode];

    if (!details || details.length === 0) {
        alert("Không có dữ liệu.");
        return;
    }

    // Thông tin chung lấy từ sản phẩm đầu tiên
    const info = details[0];

    let html = `
    <div class="order-info">

        <div class="order-title">
            <h2>📋 PHIẾU LỆNH SẢN XUẤT ỐNG LỎNG</h2>
            <span>${info.contract_code}</span>
        </div>

        <div class="order-grid">

            <div><b>Khách hàng</b><br>${info.customer_name}</div>

            <div><b>Ngày nhập</b><br>${info.import_date}</div>

            <div><b>Người lập</b><br>${info.requester}</div>

            <div><b>Người duyệt</b><br>${info.approver}</div>

            <div><b>Người vận hành</b><br>${info.operator}</div>

            <div><b>Số sản phẩm</b><br>${details.length}</div>

        </div>

    </div>

    <div class="table-container">

    <table class="detail-table">

        <thead>

            <tr>

                <th>STT</th>

                <th>Mã LT</th>

                <th>Màu ống</th>

                <th>Số sợi</th>

                <th>Đường kính</th>

                <th>Chiều dài</th>

                <th>Ngày SX</th>

                <th>Thời gian</th>

                <th>Trạng thái</th>

            </tr>

        </thead>

        <tbody>
    `;

    details.forEach((item, index) => {

        html += `

        <tr>

            <td>${index + 1}</td>

            <td>${item.loose_tube_code}</td>

            <td>${item.tube_color}</td>

            <td>${item.fiber_count}</td>

            <td>${item.diameter} mm</td>

            <td>${item.length} m</td>

            <td>${item.operation_date}</td>

            <td>${item.start_time} - ${item.end_time}</td>

            <td>

                <span class="status-badge">

                    ${item.status}

                </span>

            </td>

        </tr>

        `;

    });

    html += `

        </tbody>

    </table>

    </div>

    <div class="note-box">

        <h3>📝 Ghi chú sản xuất</h3>

        <p>${info.notes || "Không có ghi chú."}</p>

    </div>
    `;

    document.getElementById("detailBody").innerHTML = html;

    document.getElementById("detailModal").style.display = "flex";

}

const togglePwdBtn = document.getElementById("toggle-pwd-btn");
const passwordFormContainer = document.getElementById("password-form-container");

togglePwdBtn.addEventListener("click", () => {
    passwordFormContainer.classList.toggle("hidden-fields");
});

const confirmPassword =
document.getElementById("confirm-password").value;
document.getElementById("change-pwd-form").addEventListener("submit", async (e) => {

    e.preventDefault();

    const oldPassword = document.getElementById("old-password").value;
    const newPassword = document.getElementById("new-password").value;
    const confirmPassword = document.getElementById("confirm-password").value;
    const msg = document.getElementById("pwd-msg");
    msg.textContent = "";

    if (newPassword !== confirmPassword) {

        msg.style.color = "#ef4444";

        msg.textContent = "Mật khẩu nhập lại không khớp.";

        return;

    }

    try{

        const response = await fetch(`${API_URL}/change-password`,{

            method:"POST",

            headers:{
                "Content-Type":"application/json",
                "Authorization":`Bearer ${authToken}`
            },

            body:JSON.stringify({

                old_password:oldPassword,

                new_password:newPassword

            })

        });

        const result = await response.json();

        if(response.ok){

            msg.style.color="#22c55e";

            msg.textContent=result.message;

            document.getElementById("change-pwd-form").reset();

        }else{

            msg.style.color="#ef4444";

            msg.textContent=result.detail;

        }

    }catch(err){

        msg.style.color="#ef4444";

        msg.textContent="Không kết nối được máy chủ.";

    }

});