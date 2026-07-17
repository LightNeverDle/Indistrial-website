/* =====================================================================
   SMART FACTORY — FRONTEND (viết lại theo schema DB mới)
   =====================================================================
   Bảng trung tâm: cable_rolls (1 dòng = 1 lô/cuộn sản phẩm), gắn với:
     - contracts              (hợp đồng / khách hàng)
     - material_preparations  + material_preparation_items (chuẩn bị vật tư)
     - plan_loose_tube        + production_info_loose_tube  (SP: Ống Lỏng)
     - plan_sz                + production_info_sz          (SP: Bện SZ)
     - plan_jacket            + production_info_jacket      (SP: Bọc)
     - production_logs        (nhật ký cập nhật trạng thái)
     - qc_reports             (kết quả kiểm định — QC)
     - users                  (operator / prepared_by / checked_by / updated_by)

   GIẢ ĐỊNH HỢP ĐỒNG API (backend cần trả đúng format này):

   GET /api/rolls?tab=pending|processing|pending-inspect|rejected
   -> [
        {
          id, roll_code, product_type, length, current_stage, status, created_at,
          contract: { id, contract_code, customer_name, requester, approver, created_date },
          operator: "worker1" | null,
          qc: { quality_rating, checked_date } | null   // chỉ có ý nghĩa ở tab "rejected"
        }, ...
      ]

   GET /api/rolls/{id}/detail
   -> {
        roll: { id, roll_code, contract_id, product_type, length, current_stage, status, created_at },
        contract: { id, contract_code, customer_name, requester, approver, created_date, notes },
        material_preparation: { id, stage, prepared_by, prepared_date, status,
                                 items: [{ id, item_name, quantity, unit, notes }] } | null,
        production_info: [ ...mảng dòng của production_info_loose_tube / _sz / _jacket... ],
        qc_report: { id, product_code, product_type, production_length, manufacture_date,
                     quality_rating, short_fiber, broken_fiber, checked_date, checked_by, notes } | null,
        logs: [ { id, stage, status, updated_by, updated_at, notes }, ... ]
      }

   POST /api/rolls/{id}/status   body: { status: "processing" | "pending-inspect" | ... }
   ===================================================================== */

const API_URL = "http://127.0.0.1:8000/api";
let authToken = null;
let currentUsername = null;
let currentRole = null;
let currentTab = "pending";
let rollCache = {}; // cache theo id để mở modal chi tiết không phải gọi lại API list

const loginScreen = document.getElementById("login-screen");
const dashboardScreen = document.getElementById("dashboard-screen");
const taskList = document.getElementById("task-list");
const adminPanel = document.getElementById("admin-panel");
const formsPanel = document.getElementById("forms-panel");
const tabTitle = document.getElementById("tab-title");
const adminNav = document.getElementById("admin-nav");
const adminFormsNav = document.getElementById("admin-forms-nav");

const filterRollCode = document.getElementById("filter-roll-code");
const filterContractCode = document.getElementById("filter-contract-code");
const filterWorker = document.getElementById("filter-worker");
const filterProductionDate = document.getElementById("filter-production-date");
const filterShift = document.getElementById("filter-shift");
const formTypeSelect = document.getElementById("form-type-select");
const searchFormsBtn = document.getElementById("search-forms-btn");
const resetFormsBtn = document.getElementById("reset-forms-btn");

// Tiêu đề hiển thị theo từng tab (khớp trạng thái cable_rolls.status)
const TAB_TITLES = {
    pending: "Công việc đang chờ",
    processing: "Công việc đang xử lý",
    "pending-inspect": "Sản phẩm đợi kiểm định",
    rejected: "Sản phẩm/công việc bị từ chối"
};

// Nhãn hiển thị cho product_type (khớp giá trị lưu trong cable_rolls.product_type)
const PRODUCT_LABELS = {
    loose_tube: "Ống Lỏng",
    sz: "Bện SZ",
    jacket: "Bọc"
};

function productLabel(type) {
    return PRODUCT_LABELS[type] || type || "Không rõ";
}

const FORM_TYPE_CONFIG = {
    loose_tube: {
        label: "Ống lỏng",
        listEndpoint: "/loose-tube-forms",
        detailEndpoint: "/loose-tube-forms",
        detailBuilder: buildLooseTubeFormDetailHtml,
    },
    sz: {
        label: "Bện SZ",
        listEndpoint: "/sz-forms",
        detailEndpoint: "/sz-forms",
        detailBuilder: buildSzFormDetailHtml,
    },
    jacket: {
        label: "Bọc vỏ (OP)",
        listEndpoint: "/jacket-forms",
        detailEndpoint: "/jacket-forms",
        detailBuilder: buildJacketFormDetailHtml,
    },
    jacket_kcs: {
        label: "Bọc vỏ (KCS)",
        listEndpoint: "/jacket-kcs-forms",
        detailEndpoint: "/jacket-kcs-forms",
        detailBuilder: buildJacketKcsFormDetailHtml,
    },
};

function selectedFormType() {
    return formTypeSelect ? formTypeSelect.value : "loose_tube";
}

function escapeHtml(value) {
    if (value == null || value === undefined) return "";
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

// =========================================================
// 1. ĐIỀU HƯỚNG TAB
// =========================================================
document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", function () {
        document.querySelector(".nav-item.active").classList.remove("active");
        this.classList.add("active");
        const tab = this.getAttribute("data-tab");

        if (tab === "admin-panel") {
            tabTitle.textContent = "Quản lý cấp phát tài khoản";
            taskList.classList.add("hidden");
            adminPanel.classList.remove("hidden");
            formsPanel.classList.add("hidden");
            loadUsers();
        } else if (tab === "forms") {
            tabTitle.textContent = "Quản lý Phiếu Thông Tin Sản Xuất";
            taskList.classList.add("hidden");
            adminPanel.classList.add("hidden");
            formsPanel.classList.remove("hidden");
            loadForms();
        } else {
            currentTab = tab;
            taskList.classList.remove("hidden");
            adminPanel.classList.add("hidden");
            formsPanel.classList.add("hidden");
            renderRolls(tab);
        }
    });
});

// =========================================================
// 2. NÚT HÀNH ĐỘNG THEO TRẠNG THÁI CỦA cable_rolls
// =========================================================
function renderStatusButton(roll) {
    const status = roll.status || "pending";

    if (status === "completed" || status === "Hoàn thành") {
        return `<button class="btn btn-complete btn-disabled" disabled>Hoàn thành</button>`;
    }

    if (status === "processing" || status === "Đang xử lý") {
        return `<button class="btn btn-processing" onclick="updateRollStatus(${roll.id}, 'processing')">Đang xử lý → Hoàn thành</button>`;
    }

    if (status === "pending-inspect") {
        return `<button class="btn btn-secondary" disabled>Đang chờ QC kiểm định</button>`;
    }

    if (status === "rejected") {
        return `<button class="btn btn-danger-sm" onclick="updateRollStatus(${roll.id}, 'rejected')">Gửi sản xuất lại</button>`;
    }

    // Mặc định: pending -> nhận việc
    return `<button class="btn btn-confirm" onclick="updateRollStatus(${roll.id}, 'pending')">Nhận việc</button>`;
}

function stageBadge(stage) {
    if (!stage) return "";
    return `<span class="status-badge stage-badge">${stage}</span>`;
}

// =========================================================
// 3. RENDER DANH SÁCH cable_rolls THEO TAB
// =========================================================
async function renderRolls(tab) {
    tabTitle.textContent = TAB_TITLES[tab] || "Công việc";
    taskList.innerHTML = `<p style="grid-column:1/-1; text-align:center;">Đang tải dữ liệu...</p>`;

    try {
        const response = await fetch(`${API_URL}/rolls?tab=${tab}`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${authToken}` }
        });

        const data = await response.json();

        if (!response.ok) {
            taskList.innerHTML = `<p style="color:var(--error); text-align:center;">${data.detail || "Lỗi quyền truy cập"}</p>`;
            return;
        }

        taskList.innerHTML = "";

        if (!data || data.length === 0) {
            taskList.innerHTML = `<p style="grid-column:1/-1; text-align:center; color:var(--text-muted);">Không có dữ liệu nào ở mục này.</p>`;
            return;
        }

        data.forEach(roll => {
            rollCache[roll.id] = roll;

            const card = document.createElement("div");
            card.className = "task-card";
            if (tab === "pending-inspect") card.style.borderTopColor = "#f59e0b";
            if (tab === "rejected") card.style.borderTopColor = "#b92c10";

            const contract = roll.contract || {};
            const qcLine = (tab === "rejected" && roll.qc)
                ? `<p><b>Kết quả QC:</b> <span class="status-badge" style="background:var(--error)">${roll.qc.quality_rating || "Không đạt"}</span></p>`
                : "";

            const checklistLine = roll.checklist_status || (roll.in_inventory ? "Hoàn thành/Chờ giao" : null);
            const inventoryBadge = roll.in_inventory ? `<span class="status-badge" style="background:#22c55e">Nhập kho</span>` : "";

            card.innerHTML = `
                <h3 style="color:var(--primary-neon)">🧵 ${roll.roll_code}</h3>
                <p class="product-type-tag">${productLabel(roll.product_type)} ${stageBadge(roll.current_stage)}</p>
                <hr>
                <p><b>Hợp đồng:</b> ${contract.contract_code || "—"}</p>
                <p><b>Khách hàng:</b> ${contract.customer_name || "—"}</p>
                <p><b>Người vận hành:</b> ${roll.operator || "Chưa gán"}</p>
                <p><b>Chiều dài:</b> ${roll.length != null ? roll.length + " m" : "—"}</p>
                ${qcLine}
                ${checklistLine ? `<p><b>Checklist:</b> ${checklistLine} ${inventoryBadge}</p>` : ""}
                <div style="margin-top:15px">
                    <button class="btn btn-secondary" onclick="showRollDetail(${roll.id})">Chi tiết</button>
                                    ${roll.product_type === "loose_tube" ? `<button class="btn btn-secondary" onclick="showProductionFormModal(${roll.id})">Phiếu ống lỏng</button>` : ""}
                    ${roll.product_type === "sz" ? `<button class="btn btn-secondary" onclick="showProductionFormModal(${roll.id})">Phiếu Bện SZ</button>` : ""}
                    ${roll.product_type === "jacket" ? `<button class="btn btn-secondary" onclick="showProductionFormModal(${roll.id})">Phiếu Bọc Vỏ</button>` : ""}
                    ${renderStatusButton(roll)}
                </div>
            `;
            taskList.appendChild(card);
        });
    } catch (err) {
        taskList.innerHTML = `<p style="color:var(--error); text-align:center;">Không thể kết nối máy chủ.</p>`;
    }
}

// =========================================================
// 4. CẬP NHẬT TRẠNG THÁI (ghi vào production_logs + cable_rolls.status)
// =========================================================
async function updateRollStatus(rollId, currentStatus) {
    let nextStatus;
    if (currentStatus === "processing") {
        nextStatus = "pending-inspect"; // Hoàn thành công đoạn -> chuyển QC kiểm định
    } else if (currentStatus === "rejected") {
        nextStatus = "processing"; // Làm lại
    } else {
        nextStatus = "processing"; // Nhận việc
    }

    try {
        const response = await fetch(`${API_URL}/rolls/${rollId}/status`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify({ status: nextStatus })
        });

        const result = await response.json();

        if (response.ok) {
            alert(result.message || `Cập nhật trạng thái: ${nextStatus}`);
            renderRolls(currentTab);
        } else {
            alert(result.detail || "Cập nhật thất bại.");
        }
    } catch (e) {
        alert("Không thể kết nối server");
    }
}

// =========================================================
// 5. MODAL "CHI TIẾT PHIẾU LỆNH" — hỗ trợ cả 3 loại sản phẩm
// =========================================================
async function showRollDetail(rollId) {
    const modalBody = document.getElementById("detailBody");
    modalBody.innerHTML = `<p style="text-align:center;">Đang tải chi tiết...</p>`;
    document.getElementById("detailModal").style.display = "flex";

    try {
        const response = await fetch(`${API_URL}/rolls/${rollId}/detail`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${authToken}` }
        });
        const data = await response.json();

        if (!response.ok) {
            modalBody.innerHTML = `<p style="color:var(--error)">${data.detail || "Không tải được chi tiết."}</p>`;
            return;
        }

        modalBody.innerHTML = buildRollDetailHtml(data);
    } catch (err) {
        modalBody.innerHTML = `<p style="color:var(--error)">Không thể kết nối máy chủ.</p>`;
    }
}

function buildRollDetailHtml(data) {
    const roll = data.roll || {};
    const contract = data.contract || {};
    const prep = data.material_preparation;
    const qc = data.qc_report;
    const logs = data.logs || [];
    const productionForm = data.production_form;

    let html = `
        <div class="order-info">
            <div class="order-title">
                <h2>📋 PHIẾU LỆNH SẢN XUẤT — ${productLabel(roll.product_type).toUpperCase()}</h2>
                <span>${roll.roll_code || ""}</span>
            </div>
            <div class="order-grid">
                <div><b>Hợp đồng</b><br>${contract.contract_code || "—"}</div>
                <div><b>Khách hàng</b><br>${contract.customer_name || "—"}</div>
                <div><b>Người lập</b><br>${contract.requester || "—"}</div>
                <div><b>Người duyệt</b><br>${contract.approver || "—"}</div>
                <div><b>Công đoạn hiện tại</b><br>${roll.current_stage || "—"}</div>
                <div><b>Chiều dài</b><br>${roll.length != null ? roll.length + " m" : "—"}</div>
            </div>
        </div>
    `;

    // --- Bảng chuẩn bị vật tư (material_preparations + items) ---
    if (prep && prep.items && prep.items.length > 0) {
        html += `
        <div class="table-container" style="margin-top:20px">
            <h3 style="margin-bottom:10px;">🧰 Chuẩn bị vật tư</h3>
            <table class="detail-table">
                <thead><tr><th>STT</th><th>Vật tư</th><th>Số lượng</th><th>Đơn vị</th><th>Ghi chú</th></tr></thead>
                <tbody>
                    ${prep.items.map((it, idx) => `
                        <tr>
                            <td>${idx + 1}</td>
                            <td>${it.item_name || ""}</td>
                            <td>${it.quantity != null ? it.quantity : ""}</td>
                            <td>${it.unit || ""}</td>
                            <td>${it.notes || ""}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>`;
    }

    // --- Bảng sản xuất thực tế: cột khác nhau theo product_type ---
    html += buildProductionTableHtml(roll.product_type, data.production_info || []);

    // --- Thông số kỹ thuật (plan_loose_tube / plan_sz / plan_jacket) ---
    html += buildPlanInfoHtml(roll.product_type, data.plan);

    // --- Bảng form sản xuất thực tế ---
    if (productionForm) {
        html += buildProductionFormView(roll.product_type, productionForm);
    }

    if (qc) {
        const isPass = qc.quality_rating === "Đạt";
        html += `
        <div class="note-box" style="border-left-color:${isPass ? '#22c55e' : '#ef4444'}">
            <h3 style="color:${isPass ? '#22c55e' : '#ef4444'}">🔍 Kết quả kiểm định (QC)</h3>
            <p><b>Mã sản phẩm:</b> ${qc.product_code || "—"} &nbsp;|&nbsp; <b>Kết quả:</b> ${qc.quality_rating || "—"}</p>
            <p><b>Sợi ngắn:</b> ${qc.short_fiber ?? "—"} &nbsp;|&nbsp; <b>Sợi đứt:</b> ${qc.broken_fiber ?? "—"}</p>
            <p><b>Ngày kiểm:</b> ${qc.checked_date || "—"} &nbsp;|&nbsp; <b>Ca sản xuất:</b> ${qc.shift || "—"}</p>
            <p>${qc.notes || ""}</p>
        </div>`;
    }

    if (currentRole === "admin" || currentRole === "inspector") {
        html += buildQcFormHtml(roll, qc);
    }

    // --- Thông tin tồn kho / checklist ---
    if (data.inventory) {
        const inv = data.inventory;
        html += `
        <div class="note-box" style="border-left-color:#22c55e; margin-top:15px;">
            <h3 style="color:#22c55e">🏷️ Thông tin kho</h3>
            <p><b>Mã sản phẩm:</b> ${inv.product_code || "—"} &nbsp;|&nbsp; <b>Loại:</b> ${inv.product_type || "—"}</p>
            <p><b>Chiều dài:</b> ${inv.length != null ? inv.length + (inv.length > 10 ? " m" : "") : "—"} &nbsp;|&nbsp; <b>Số lượng:</b> ${inv.quantity || 1}</p>
            <p><b>Ngày nhập:</b> ${inv.stored_date || "—"} &nbsp;|&nbsp; <b>Vị trí:</b> ${inv.location || "—"}</p>
            <p>${inv.notes || ""}</p>
        </div>`;
    } else if (data.roll && data.roll.checklist_status) {
        html += `
        <div class="note-box" style="border-left-color:#f59e0b; margin-top:15px;">
            <h3 style="color:#f59e0b">📦 Checklist</h3>
            <p><b>Trạng thái checklist:</b> ${data.roll.checklist_status}</p>
        </div>`;
    }

    // --- Lịch sử cập nhật (production_logs) ---
    if (logs.length > 0) {
        html += `
        <div class="table-container" style="margin-top:20px">
            <h3 style="margin-bottom:10px;">🕒 Lịch sử cập nhật</h3>
            <table class="detail-table">
                <thead><tr><th>Công đoạn</th><th>Trạng thái</th><th>Người cập nhật</th><th>Thời gian</th><th>Ghi chú</th></tr></thead>
                <tbody>
                    ${logs.map(l => `
                        <tr>
                            <td>${l.stage || ""}</td>
                            <td><span class="status-badge">${l.status || ""}</span></td>
                            <td>${l.updated_by || ""}</td>
                            <td>${l.updated_at || ""}</td>
                            <td>${l.notes || ""}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>`;
    }

    return html;
}

// Cấu hình cột hiển thị riêng cho từng loại sản phẩm
// (khớp đúng tên cột của production_info_loose_tube / _sz / _jacket)
const PRODUCTION_COLUMNS = {
    loose_tube: [
        { key: "stt", label: "STT" },
        { key: "tube_code", label: "Mã ống lỏng" },
        { key: "color", label: "Màu ống lỏng" },
        { key: "fiber_count", label: "Số sợi" },
        { key: "diameter", label: "Đường kính" },
        { key: "length", label: "Chiều dài", suffix: " m" },
        { key: "production_date", label: "Ngày sản xuất" }
    ],
    sz: [
        { key: "stt", label: "STT" },
        { key: "core_code", label: "Mã số sản phẩm" },
        { key: "length", label: "Chiều dài", suffix: " m" },
        { key: "tube_duong", label: "Dương" },
        { key: "tube_cam", label: "Cam" },
        { key: "tube_luc", label: "Lục" },
        { key: "tube_nau", label: "Nâu" },
        { key: "filler", label: "Filler" }
    ],
    jacket: [
        { key: "stt", label: "STT" },
        { key: "cable_code", label: "Mã cuộn cáp" },
        { key: "core_code", label: "Mã lõi" },
        { key: "product_label", label: "Thông tin trên vỏ cáp" },
        { key: "length", label: "Chiều dài", suffix: " km" }
    ]
};

// Nhãn hiển thị cho các trường thông số kỹ thuật (plan_loose_tube / plan_sz / plan_jacket)
const PLAN_LABELS = {
    loose_tube: [
        { key: "fiber_count", label: "Số sợi" },
        { key: "diameter", label: "Đường kính", suffix: " mm" },
        { key: "tube_color", label: "Màu ống lỏng" },
        { key: "operation_date", label: "Ngày sản xuất" },
        { key: "notes", label: "Ghi chú" }
    ],
    sz: [
        { key: "fpr_type", label: "Chủng loại FPR" },
        { key: "fpr_lot", label: "Lô số FPR" },
        { key: "binder_type", label: "Chủng loại chỉ bện" },
        { key: "binder_lot", label: "Lô số chỉ bện" },
        { key: "spec_summary", label: "Tiêu chuẩn kỹ thuật" },
        { key: "notes", label: "Ghi chú" }
    ],
    jacket: [
        { key: "thickness", label: "Độ dày vỏ", suffix: " mm" },
        { key: "ripcord_count", label: "Chỉ xé cáp" },
        { key: "hanging_steel", label: "Thép treo" },
        { key: "armor", label: "Giáp bảo vệ" },
        { key: "notes", label: "Ghi chú" }
    ]
};

function buildQcFormHtml(roll, qc) {
    const today = new Date().toISOString().slice(0, 10);
    const currentDate = qc?.checked_date ? qc.checked_date.slice(0, 10) : today;

    return `
    <div class="table-container" style="margin-top:20px">
        <h3 style="margin-bottom:10px;">✅ Phiếu QC</h3>
        <form onsubmit="submitQcReport(event, ${roll.id})">
            <div class="form-grid">
                <div class="input-group">
                    <label>Mã số sản phẩm</label>
                    <input name="product_code" value="${escapeHtml(qc?.product_code || roll.roll_code || "")}" required>
                </div>
                <div class="input-group">
                    <label>Loại sản phẩm</label>
                    <input name="product_type" value="${escapeHtml(qc?.product_type || productLabel(roll.product_type))}" required>
                </div>
                <div class="input-group">
                    <label>Chiều dài sản xuất (m)</label>
                    <input type="number" step="0.01" name="production_length" value="${escapeHtml(qc?.production_length ?? roll.length ?? "")}">
                </div>
                <div class="input-group">
                    <label>Ngày sản xuất</label>
                    <input type="date" name="manufacture_date" value="${escapeHtml(qc?.manufacture_date || "")}">
                </div>
                <div class="input-group">
                    <label>Ca sản xuất</label>
                    <input name="shift" value="${escapeHtml(qc?.shift || "")}">
                </div>
                <div class="input-group">
                    <label>Đánh giá chất lượng</label>
                    <select name="quality_rating">
                        <option value="Đạt" ${qc?.quality_rating === "Đạt" ? "selected" : ""}>Đạt</option>
                        <option value="Không đạt" ${qc?.quality_rating === "Không đạt" ? "selected" : ""}>Không đạt</option>
                    </select>
                </div>
                <div class="input-group">
                    <label>Sợi ngắn</label>
                    <input type="number" min="0" name="short_fiber" value="${escapeHtml(qc?.short_fiber ?? "")}">
                </div>
                <div class="input-group">
                    <label>Sợi dài / đứt</label>
                    <input type="number" min="0" name="broken_fiber" value="${escapeHtml(qc?.broken_fiber ?? "")}">
                </div>
                <div class="input-group">
                    <label>Ngày kiểm tra</label>
                    <input type="date" name="checked_date" value="${escapeHtml(currentDate)}">
                </div>
                <div class="input-group">
                    <label>Người kiểm tra</label>
                    <input name="checked_by" value="${escapeHtml(currentUsername || "")}" readonly>
                </div>
            </div>
            <div class="input-group">
                <label>Ghi chú</label>
                <textarea name="notes" rows="3">${escapeHtml(qc?.notes || "")}</textarea>
            </div>
            <button type="submit" class="btn btn-primary">Lưu kết quả QC</button>
        </form>
    </div>`;
}

async function submitQcReport(event, rollId) {
    event.preventDefault();
    const form = event.target;
    const payload = {
        product_code: form.product_code.value.trim(),
        product_type: form.product_type.value.trim(),
        production_length: form.production_length.value ? Number(form.production_length.value) : null,
        manufacture_date: form.manufacture_date.value || null,
        shift: form.shift.value.trim() || null,
        quality_rating: form.quality_rating.value,
        short_fiber: form.short_fiber.value ? Number(form.short_fiber.value) : null,
        broken_fiber: form.broken_fiber.value ? Number(form.broken_fiber.value) : null,
        checked_date: form.checked_date.value || null,
        notes: form.notes.value.trim() || null,
    };

    try {
        const response = await fetch(`${API_URL}/rolls/${rollId}/qc`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        if (response.ok) {
            alert(result.message || "Đã lưu kết quả QC");
            showRollDetail(rollId);
            renderRolls(currentTab);
        } else {
            alert(result.detail || "Lưu QC thất bại.");
        }
    } catch (err) {
        alert("Không thể kết nối máy chủ.");
    }
}

function buildPlanInfoHtml(productType, plan) {
    const fields = PLAN_LABELS[productType];
    if (!plan || !fields) return "";

    const cells = fields
        .filter(f => plan[f.key] !== null && plan[f.key] !== undefined && plan[f.key] !== "")
        .map(f => `<div><b>${f.label}</b><br>${plan[f.key]}${f.suffix || ""}</div>`)
        .join("");

    if (!cells) return "";

    return `
    <div class="order-info" style="margin-top:20px">
        <div class="order-title"><h2 style="font-size:1rem">⚙️ Thông số kỹ thuật</h2></div>
        <div class="order-grid">${cells}</div>
    </div>`;
}

function buildProductionTableHtml(productType, rows) {
    const columns = PRODUCTION_COLUMNS[productType];
    if (!columns || !rows || rows.length === 0) {
        return `<div class="note-box"><p>Chưa có dữ liệu sản xuất thực tế cho lô này.</p></div>`;
    }

    return `
    <div class="table-container" style="margin-top:20px">
        <h3 style="margin-bottom:10px;">⚙️ Thông tin sản xuất — ${productLabel(productType)}</h3>
        <table class="detail-table">
            <thead>
                <tr>${columns.map(c => `<th>${c.label}</th>`).join("")}</tr>
            </thead>
            <tbody>
                ${rows.map(row => `
                    <tr>
                        ${columns.map(c => `<td>${row[c.key] != null ? row[c.key] + (c.suffix || "") : "—"}</td>`).join("")}
                    </tr>
                `).join("")}
            </tbody>
        </table>
    </div>`;
}

// =========================================================
// 6. ĐĂNG NHẬP
// =========================================================
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
            currentUsername = result.username;
            currentRole = result.role;

            document.getElementById("user-display").textContent = result.username.toUpperCase();
            document.getElementById("role-display").textContent = result.role.toUpperCase();

            if (result.role === "admin") {
                adminNav.classList.remove("hidden");
                adminFormsNav.classList.remove("hidden");
            } else {
                adminNav.classList.add("hidden");
                adminFormsNav.classList.add("hidden");
            }

            loginScreen.classList.add("hidden");
            dashboardScreen.classList.remove("hidden");

            currentTab = "pending";
            renderRolls("pending");
        } else {
            loginError.textContent = result.detail;
        }
    } catch (err) {
        loginError.textContent = "Không thể kết nối đến máy chủ.";
    }
});

// =========================================================
// 7. QUẢN LÝ TÀI KHOẢN (users) — giữ nguyên logic cũ
// =========================================================
async function loadUsers() {
    const tbody = document.getElementById("user-table-body");
    tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:var(--text-muted);">Đang tải dữ liệu...</td></tr>`;
    try {
        const response = await fetch(`${API_URL}/users`, {
            headers: { "Authorization": `Bearer ${authToken}` }
        });
        const users = await response.json();
        tbody.innerHTML = "";
        users.forEach(user => {
            const tr = document.createElement("tr");
            const deleteButton = user.username === "admin"
                ? `<span style="color:var(--text-muted); font-size:0.8rem;">Hệ thống bảo vệ</span>`
                : `<button class="btn-delete-task" onclick="deleteUser('${user.username}')">Xóa</button>`;
            tr.innerHTML = `<td><strong>${user.username}</strong></td><td><span class="highlight">${(user.role || "").toUpperCase()}</span></td><td>${deleteButton}</td>`;
            tbody.appendChild(tr);
        });
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:var(--error);">Lỗi tải dữ liệu.</td></tr>`;
    }
}

document.getElementById("create-user-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("new-user-name").value.trim();
    const password = document.getElementById("new-user-pass").value;
    const role = document.getElementById("new-user-role").value;
    const msg = document.getElementById("admin-msg");
    const err = document.getElementById("admin-error");
    msg.textContent = "";
    err.textContent = "";

    try {
        const response = await fetch(`${API_URL}/users`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify({ username, password, role })
        });
        const result = await response.json();

        if (response.ok) {
            msg.textContent = result.message || "Tạo tài khoản thành công.";
            document.getElementById("create-user-form").reset();
            loadUsers();
        } else {
            err.textContent = result.detail || "Tạo tài khoản thất bại.";
        }
    } catch (e2) {
        err.textContent = "Không thể kết nối máy chủ.";
    }
});

async function deleteUser(username) {
    if (!confirm(`Xóa tài khoản "${username}"?`)) return;
    try {
        const response = await fetch(`${API_URL}/users/${username}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${authToken}` }
        });
        const result = await response.json();
        if (response.ok) {
            loadUsers();
        } else {
            alert(result.detail || "Xóa thất bại.");
        }
    } catch (err) {
        alert("Không thể kết nối máy chủ.");
    }
}

// =========================================================
// 7B. NHẬT KÝ THAO TÁC (AUDIT LOG) — chỉ admin xem được
// =========================================================
const ROLE_LABELS = {
    admin: "Admin",
    worker1: "Worker 1",
    worker2: "Worker 2",
    worker3: "Worker 3",
    inspector: "Inspector"
};

const ACTION_LABELS = {
    LOGIN: "Đăng nhập",
    CHANGE_PASSWORD: "Đổi mật khẩu",
    UPDATE_ROLL_STATUS: "Cập nhật trạng thái lô",
    CREATE_USER: "Tạo tài khoản",
    DELETE_USER: "Xóa tài khoản"
};

async function loadForms() {
    const tbody = document.getElementById("forms-table-body");
    const formType = selectedFormType();
    const config = FORM_TYPE_CONFIG[formType] || FORM_TYPE_CONFIG.loose_tube;

    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">Đang tải dữ liệu...</td></tr>`;
    try {
        const params = new URLSearchParams();
        if (filterRollCode.value.trim()) params.append("roll_code", filterRollCode.value.trim());
        if (filterContractCode.value.trim()) params.append("contract_code", filterContractCode.value.trim());
        if (filterWorker.value.trim()) params.append("worker", filterWorker.value.trim());
        if (filterProductionDate.value) params.append("production_date", filterProductionDate.value);
        if (filterShift.value.trim()) params.append("shift", filterShift.value.trim());

        const response = await fetch(`${API_URL}${config.listEndpoint}?${params.toString()}`, {
            headers: { "Authorization": `Bearer ${authToken}` }
        });
        const forms = await response.json();
        tbody.innerHTML = "";
        if (!response.ok) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--error);">${forms.detail || "Lỗi tải dữ liệu."}</td></tr>`;
            return;
        }
        if (!forms.length) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">Không tìm thấy phiếu nào.</td></tr>`;
            return;
        }
        forms.forEach(form => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${form.id}</td>
                <td>${escapeHtml(form.roll_code || "—")}</td>
                <td>${escapeHtml(form.contract_code || "—")}</td>
                <td>${escapeHtml(form.worker || "—")}</td>
                <td>${escapeHtml(form.production_date || "—")}</td>
                <td>${escapeHtml(form.shift || "—")}</td>
                <td><span class="status-badge">${escapeHtml(form.form_status || "—")}</span></td>
                <td><button class="btn btn-secondary" onclick="showFormDetail(${form.id})">Xem</button></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--error);">Không thể kết nối máy chủ.</td></tr>`;
    }
}

document.getElementById("search-forms-btn").addEventListener("click", (e) => {
    e.preventDefault();
    loadForms();
});

document.getElementById("reset-forms-btn").addEventListener("click", (e) => {
    e.preventDefault();
    filterRollCode.value = "";
    filterContractCode.value = "";
    filterWorker.value = "";
    filterProductionDate.value = "";
    filterShift.value = "";
    loadForms();
});

if (formTypeSelect) {
    formTypeSelect.addEventListener("change", () => {
        loadForms();
    });
}

const viewAuditLogBtn = document.getElementById("view-audit-log-btn");
if (viewAuditLogBtn) {
    viewAuditLogBtn.addEventListener("click", (e) => {
        e.preventDefault();
        showAuditLog("all");
    });
}

function buildLooseTubeFormView(looseForm) {
    return `
    <div class="table-container" style="margin-top:20px">
        <h3 style="margin-bottom:10px;">📝 Phiếu Thông Tin Ống Lỏng đã nhập</h3>
        <div class="order-grid">
            <div><b>STT</b><br>${escapeHtml(looseForm.stt || "—")}</div>
            <div><b>Mã sợi</b><br>${escapeHtml(looseForm.fiber_code || "—")}</div>
            <div><b>Ca sản xuất</b><br>${escapeHtml(looseForm.shift || "—")}</div>
            <div><b>Mã ống lỏng</b><br>${escapeHtml(looseForm.tube_code || "—")}</div>
            <div><b>Tốc độ máy</b><br>${looseForm.machine_speed != null ? looseForm.machine_speed + " m/min" : "—"}</div>
            <div><b>Màu</b><br>${escapeHtml(looseForm.color || "—")}</div>
            <div><b>Số sợi</b><br>${escapeHtml(looseForm.fiber_count || "—")}</div>
            <div><b>Đường kính</b><br>${looseForm.diameter != null ? looseForm.diameter + " mm" : "—"}</div>
            <div><b>Chiều dài</b><br>${looseForm.length != null ? looseForm.length + " m" : "—"}</div>
            <div><b>Ngày sản xuất</b><br>${escapeHtml(looseForm.production_date || "—")}</div>
            <div><b>Số bobbin</b><br>${escapeHtml(looseForm.bobbin_count || "—")}</div>
            <div><b>Người nhập</b><br>${escapeHtml(looseForm.operator_name || "—")}</div>
            <div style="grid-column: span 3;"><b>Ghi chú</b><br>${escapeHtml(looseForm.notes || "—")}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(looseForm.form_status || "—")}</div>
        </div>
    </div>`;
}

function buildSzFormView(form) {
    return `
    <div class="table-container" style="margin-top:20px">
        <h3 style="margin-bottom:10px;">📝 Phiếu Thông Tin Bện SZ đã nhập</h3>
        <div class="order-grid">
            <div><b>STT</b><br>${escapeHtml(form.stt || "—")}</div>
            <div><b>Mã lõi</b><br>${escapeHtml(form.core_code || "—")}</div>
            <div><b>Ca sản xuất</b><br>${escapeHtml(form.shift || "—")}</div>
            <div><b>Chiều dài</b><br>${form.length != null ? form.length + " m" : "—"}</div>
            <div><b>Ống Dương</b><br>${escapeHtml(form.tube_duong || "—")}</div>
            <div><b>Ống Cam</b><br>${escapeHtml(form.tube_cam || "—")}</div>
            <div><b>Ống Lục</b><br>${escapeHtml(form.tube_luc || "—")}</div>
            <div><b>Ống Nâu</b><br>${escapeHtml(form.tube_nau || "—")}</div>
            <div><b>Filler</b><br>${escapeHtml(form.filler || "—")}</div>
            <div><b>Ngày sản xuất</b><br>${escapeHtml(form.production_date || "—")}</div>
            <div><b>Người nhập</b><br>${escapeHtml(form.operator_name || "—")}</div>
            <div style="grid-column: span 3;"><b>Ghi chú</b><br>${escapeHtml(form.notes || "—")}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(form.form_status || "—")}</div>
        </div>
    </div>`;
}

function buildJacketFormView(form) {
    return `
    <div class="table-container" style="margin-top:20px">
        <h3 style="margin-bottom:10px;">📝 Phiếu Thông Tin Bọc Vỏ đã nhập</h3>
        <div class="order-grid">
            <div><b>STT</b><br>${escapeHtml(form.stt || "—")}</div>
            <div><b>Mã cuộn cáp</b><br>${escapeHtml(form.cable_code || "—")}</div>
            <div><b>Mã lõi</b><br>${escapeHtml(form.core_code || "—")}</div>
            <div><b>Thông tin vỏ cáp</b><br>${escapeHtml(form.product_label || "—")}</div>
            <div><b>Chiều dài</b><br>${form.length != null ? form.length + " m" : "—"}</div>
            <div><b>Loại sản phẩm</b><br>${escapeHtml(form.product_type || "—")}</div>
            <div><b>Mã lô lỗi</b><br>${escapeHtml(form.error_roll_code || "—")}</div>
            <div><b>Ngày sản xuất</b><br>${escapeHtml(form.manufacture_date || "—")}</div>
            <div><b>BL1</b><br>${escapeHtml(form.bl1 || "—")}</div>
            <div><b>Đầu</b><br>${form.head_length != null ? form.head_length + " m" : "—"}</div>
            <div><b>Đuôi</b><br>${form.tail_length != null ? form.tail_length + " m" : "—"}</div>
            <div><b>Người nhập</b><br>${escapeHtml(form.operator_name || "—")}</div>
            <div style="grid-column: span 3;"><b>Ghi chú</b><br>${escapeHtml(form.notes || "—")}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(form.form_status || "—")}</div>
        </div>
    </div>`;
}

function buildJacketKcsFormView(form) {
    return `
    <div class="table-container" style="margin-top:20px">
        <h3 style="margin-bottom:10px;">📝 Phiếu Thông Tin KCS Bọc Vỏ đã nhập</h3>
        <div class="order-grid">
            <div><b>STT</b><br>${escapeHtml(form.stt || "—")}</div>
            <div><b>Mã cuộn cáp</b><br>${escapeHtml(form.cable_code || "—")}</div>
            <div><b>Mã lõi</b><br>${escapeHtml(form.core_code || "—")}</div>
            <div><b>Thông tin vỏ cáp</b><br>${escapeHtml(form.product_label || "—")}</div>
            <div><b>Chiều dài</b><br>${form.length != null ? form.length + " m" : "—"}</div>
            <div><b>Loại sản phẩm</b><br>${escapeHtml(form.product_type || "—")}</div>
            <div><b>Mã lô lỗi</b><br>${escapeHtml(form.error_roll_code || "—")}</div>
            <div><b>Ngày kiểm</b><br>${escapeHtml(form.manufacture_date || "—")}</div>
            <div><b>Kết quả KCS</b><br>${escapeHtml(form.inspection_result || "—")}</div>
            <div style="grid-column: span 3;"><b>Ghi chú KCS</b><br>${escapeHtml(form.inspection_notes || "—")}</div>
            <div><b>Người nhập</b><br>${escapeHtml(form.operator_name || "—")}</div>
            <div style="grid-column: span 3;"><b>Ghi chú tổng</b><br>${escapeHtml(form.notes || "—")}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(form.form_status || "—")}</div>
        </div>
    </div>`;
}

function buildProductionFormView(productType, form) {
    if (productType === "loose_tube") return buildLooseTubeFormView(form);
    if (productType === "sz") return buildSzFormView(form);
    if (productType === "jacket") {
        return form.inspection_result ? buildJacketKcsFormView(form) : buildJacketFormView(form);
    }
    return "";
}

async function showProductionFormModal(rollId) {
    const modalBody = document.getElementById("detailBody");
    modalBody.innerHTML = `<p style="text-align:center;">Đang tải phiếu sản xuất...</p>`;
    document.getElementById("detailModal").style.display = "flex";

    try {
        const response = await fetch(`${API_URL}/rolls/${rollId}/detail`, {
            headers: { "Authorization": `Bearer ${authToken}` }
        });
        const data = await response.json();
        if (!response.ok) {
            modalBody.innerHTML = `<p style="color:var(--error)">${data.detail || "Không tải được dữ liệu."}</p>`;
            return;
        }

        const roll = data.roll || {};
        const form = data.production_form || {};
        if (roll.product_type === "loose_tube") {
            modalBody.innerHTML = buildLooseTubeFormEditor(roll, form);
        } else if (roll.product_type === "sz") {
            modalBody.innerHTML = buildSzFormEditor(roll, form);
        } else if (roll.product_type === "jacket") {
            if (form.inspection_result) {
                modalBody.innerHTML = buildJacketKcsFormEditor(roll, form);
            } else {
                modalBody.innerHTML = buildJacketFormEditor(roll, form);
            }
        } else {
            modalBody.innerHTML = `<p style="color:var(--error)">Loại phiếu không hỗ trợ.</p>`;
        }
    } catch (err) {
        modalBody.innerHTML = `<p style="color:var(--error)">Không thể kết nối máy chủ.</p>`;
    }
}

function buildLooseTubeFormEditor(roll, looseForm) {
    const today = new Date().toISOString().slice(0, 10);
    return `
    <div class="order-info">
        <div class="order-title">
            <h2>📝 NHẬP PHIẾU ỐNG LỎNG</h2>
            <span>${escapeHtml(roll.roll_code || "")}</span>
        </div>
        <div class="order-grid">
            <div><b>Roll</b><br>${escapeHtml(roll.roll_code || "—")}</div>
            <div><b>Loại</b><br>${escapeHtml(productLabel(roll.product_type))}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(roll.status || "—")}</div>
        </div>
    </div>
    <form onsubmit="submitLooseTubeForm(event, ${roll.id})">
        <div class="form-grid" style="margin-top:20px;">
            <div class="input-group">
                <label>STT</label>
                <input type="number" name="stt" value="${escapeHtml(looseForm.stt || "")}">
            </div>
            <div class="input-group">
                <label>Mã sợi</label>
                <input name="fiber_code" value="${escapeHtml(looseForm.fiber_code || "")}">
            </div>
            <div class="input-group">
                <label>Ca sản xuất</label>
                <input name="shift" value="${escapeHtml(looseForm.shift || "")}">
            </div>
            <div class="input-group">
                <label>Mã ống lỏng</label>
                <input name="tube_code" value="${escapeHtml(looseForm.tube_code || "")}">
            </div>
            <div class="input-group">
                <label>Tốc độ máy</label>
                <input type="number" step="0.01" name="machine_speed" value="${escapeHtml(looseForm.machine_speed || "")}">
            </div>
            <div class="input-group">
                <label>Màu</label>
                <input name="color" value="${escapeHtml(looseForm.color || "")}">
            </div>
            <div class="input-group">
                <label>Số sợi</label>
                <input type="number" name="fiber_count" value="${escapeHtml(looseForm.fiber_count || "")}">
            </div>
            <div class="input-group">
                <label>Đường kính</label>
                <input type="number" step="0.01" name="diameter" value="${escapeHtml(looseForm.diameter || "")}">
            </div>
            <div class="input-group">
                <label>Chiều dài (m)</label>
                <input type="number" step="0.01" name="length" value="${escapeHtml(looseForm.length || "")}">
            </div>
            <div class="input-group">
                <label>Ngày sản xuất</label>
                <input type="date" name="production_date" value="${escapeHtml(looseForm.production_date || today)}">
            </div>
            <div class="input-group">
                <label>Số bobbin</label>
                <input type="number" name="bobbin_count" value="${escapeHtml(looseForm.bobbin_count || "")}">
            </div>
        </div>
        <div class="input-group" style="margin-top:10px;">
            <label>Ghi chú</label>
            <textarea name="notes" rows="4">${escapeHtml(looseForm.notes || "")}</textarea>
        </div>
        <button type="submit" class="btn btn-primary" style="margin-top:20px;">Lưu phiếu</button>
    </form>`;
}

function buildSzFormEditor(roll, szForm) {
    const today = new Date().toISOString().slice(0, 10);
    return `
    <div class="order-info">
        <div class="order-title">
            <h2>📝 NHẬP PHIẾU BỆN SZ</h2>
            <span>${escapeHtml(roll.roll_code || "")}</span>
        </div>
        <div class="order-grid">
            <div><b>Roll</b><br>${escapeHtml(roll.roll_code || "—")}</div>
            <div><b>Loại</b><br>${escapeHtml(productLabel(roll.product_type))}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(roll.status || "—")}</div>
        </div>
    </div>
    <form onsubmit="submitSzForm(event, ${roll.id})">
        <div class="form-grid" style="margin-top:20px;">
            <div class="input-group">
                <label>STT</label>
                <input type="number" name="stt" value="${escapeHtml(szForm.stt || "")}">
            </div>
            <div class="input-group">
                <label>Mã sản phẩm</label>
                <input name="product_code" value="${escapeHtml(szForm.product_code || "")}">
            </div>
            <div class="input-group">
                <label>Mã cuộn</label>
                <input name="core_code" value="${escapeHtml(szForm.core_code || "")}">
            </div>
            <div class="input-group">
                <label>Ca sản xuất</label>
                <input name="shift" value="${escapeHtml(szForm.shift || "")}">
            </div>
            <div class="input-group">
                <label>Ngày sản xuất</label>
                <input type="date" name="production_date" value="${escapeHtml(szForm.production_date || today)}">
            </div>
            <div class="input-group">
                <label>Máy bện SZ</label>
                <input name="machine" value="${escapeHtml(szForm.machine || "")}">
            </div>
            <div class="input-group">
                <label>Tốc độ máy</label>
                <input type="number" step="0.01" name="machine_speed" value="${escapeHtml(szForm.machine_speed || "")}">
            </div>
            <div class="input-group">
                <label>Chiều dài sản xuất (m)</label>
                <input type="number" step="0.01" name="length" value="${escapeHtml(szForm.length || "")}">
            </div>
            <div class="input-group">
                <label>Bước bện (SZ Pitch)</label>
                <input name="sz_pitch" value="${escapeHtml(szForm.sz_pitch || "")}">
            </div>
            <div class="input-group">
                <label>Hướng bện</label>
                <input name="lay_direction" value="${escapeHtml(szForm.lay_direction || "")}">
            </div>
            <div class="input-group">
                <label>Lực căng</label>
                <input name="tension" value="${escapeHtml(szForm.tension || "")}">
            </div>
            <div class="input-group">
                <label>Tốc độ kéo</label>
                <input type="number" step="0.01" name="pull_speed" value="${escapeHtml(szForm.pull_speed || "")}">
            </div>
            <div class="input-group">
                <label>Đường kính sau bện</label>
                <input type="number" step="0.01" name="post_braid_diameter" value="${escapeHtml(szForm.post_braid_diameter || "")}">
            </div>
        </div>
        <div class="form-grid" style="margin-top:20px;">
            <div class="input-group">
                <label>Đường kính KCS</label>
                <input type="number" step="0.01" name="kcs_diameter" value="${escapeHtml(szForm.kcs_diameter || "")}">
            </div>
            <div class="input-group">
                <label>Độ đồng đều</label>
                <input name="kcs_uniformity" value="${escapeHtml(szForm.kcs_uniformity || "")}">
            </div>
            <div class="input-group">
                <label>Kiểm tra ngoại quan</label>
                <input name="kcs_external_inspection" value="${escapeHtml(szForm.kcs_external_inspection || "")}">
            </div>
            <div class="input-group" style="grid-column: span 3;">
                <label>Ghi chú KCS</label>
                <textarea name="kcs_notes" rows="4">${escapeHtml(szForm.kcs_notes || "")}</textarea>
            </div>
        </div>
        <div class="input-group" style="margin-top:10px;">
            <label>Ghi chú tổng</label>
            <textarea name="notes" rows="4">${escapeHtml(szForm.notes || "")}</textarea>
        </div>
        <button type="submit" class="btn btn-primary" style="margin-top:20px;">Lưu phiếu</button>
    </form>`;
}

function buildJacketFormEditor(roll, jacketForm) {
    const today = new Date().toISOString().slice(0, 10);
    return `
    <div class="order-info">
        <div class="order-title">
            <h2>📝 NHẬP PHIẾU BỌC VỎ</h2>
            <span>${escapeHtml(roll.roll_code || "")}</span>
        </div>
        <div class="order-grid">
            <div><b>Roll</b><br>${escapeHtml(roll.roll_code || "—")}</div>
            <div><b>Loại</b><br>${escapeHtml(productLabel(roll.product_type))}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(roll.status || "—")}</div>
        </div>
    </div>
    <form onsubmit="submitJacketForm(event, ${roll.id})">
        <div class="form-grid" style="margin-top:20px;">
            <div class="input-group">
                <label>STT</label>
                <input type="number" name="stt" value="${escapeHtml(jacketForm.stt || "")}">
            </div>
            <div class="input-group">
                <label>Mã số cáp thành phẩm</label>
                <input name="cable_code" value="${escapeHtml(jacketForm.cable_code || "")}">
            </div>
            <div class="input-group">
                <label>Mã số cuộn lõi</label>
                <input name="core_code" value="${escapeHtml(jacketForm.core_code || "")}">
            </div>
            <div class="input-group">
                <label>Thông tin vỏ cáp</label>
                <input name="product_label" value="${escapeHtml(jacketForm.product_label || "")}">
            </div>
            <div class="input-group">
                <label>Chủng loại sản phẩm</label>
                <input name="product_type" value="${escapeHtml(jacketForm.product_type || "")}">
            </div>
            <div class="input-group">
                <label>Ngày sản xuất</label>
                <input type="date" name="manufacture_date" value="${escapeHtml(jacketForm.manufacture_date || today)}">
            </div>
            <div class="input-group">
                <label>Ca sản xuất</label>
                <input name="shift" value="${escapeHtml(jacketForm.shift || "")}">
            </div>
            <div class="input-group">
                <label>Bin</label>
                <input name="bin" value="${escapeHtml(jacketForm.bin || "")}">
            </div>
            <div class="input-group">
                <label>FRP</label>
                <input name="frp" value="${escapeHtml(jacketForm.frp || "")}">
            </div>
            <div class="input-group">
                <label>Loại nhựa BL1</label>
                <input name="bl1" value="${escapeHtml(jacketForm.bl1 || "")}">
            </div>
            <div class="input-group">
                <label>Chiều dài đầu</label>
                <input type="number" step="0.01" name="head_length" value="${escapeHtml(jacketForm.head_length || "")}">
            </div>
            <div class="input-group">
                <label>Chiều dài cuối</label>
                <input type="number" step="0.01" name="tail_length" value="${escapeHtml(jacketForm.tail_length || "")}">
            </div>
        </div>
        <div class="order-info" style="margin-top:20px;">
            <div class="order-title"><h3>📊 KCS</h3></div>
        </div>
        <div class="form-grid">
            <div class="input-group">
                <label>Chiều dài đo (m)</label>
                <input type="number" step="0.01" name="measured_length" value="${escapeHtml(jacketForm.measured_length || "")}">
            </div>
            <div class="input-group">
                <label>Kết quả suy hao</label>
                <input name="loss_result" value="${escapeHtml(jacketForm.loss_result || "")}">
            </div>
            <div class="input-group">
                <label>Người đo</label>
                <input name="measured_by" value="${escapeHtml(jacketForm.measured_by || "")}">
            </div>
            <div class="input-group" style="grid-column: span 2;">
                <label>Ghi chú</label>
                <textarea name="notes" rows="4">${escapeHtml(jacketForm.notes || "")}</textarea>
            </div>
        </div>
        <div class="order-info" style="margin-top:20px;">
            <div class="order-title"><h3>🎨 KCS Theo Màu</h3></div>
        </div>
        <div class="kcs-measurements">
            ${buildJacketKcsInputs(jacketForm)}
        </div>
        <button type="submit" class="btn btn-primary" style="margin-top:20px;">Lưu phiếu</button>
    </form>`;
}

function buildJacketKcsInputs(jacketForm) {
    const colors = ["Dương", "Cam", "Lục", "Nâu", "Xám", "Trắng"];
    const jsonData = jacketForm.kcs_measurements ? parseJsonSafe(jacketForm.kcs_measurements) : {};

    return colors.map(color => {
        const group = jsonData[color] || Array.from({ length: 12 }, () => ({ loss_1310: "", loss_1550: "" }));
        return `
            <div class="kcs-group">
                <h4>${color}</h4>
                <div class="kcs-grid">
                    <div><b>Sợi</b></div>
                    <div><b>1310nm</b></div>
                    <div><b>1550nm</b></div>
                    ${group.map((fiber, idx) => `
                        <div>${idx + 1}</div>
                        <div><input type="number" step="0.01" name="kcs_${color}_1310_${idx}" value="${escapeHtml(fiber.loss_1310 || "")}"></div>
                        <div><input type="number" step="0.01" name="kcs_${color}_1550_${idx}" value="${escapeHtml(fiber.loss_1550 || "")}"></div>
                    `).join("")}
                </div>
            </div>
        `;
    }).join("");
}

function parseJsonSafe(value) {
    if (!value) return {};
    try {
        return typeof value === "string" ? JSON.parse(value) : value;
    } catch (e) {
        return {};
    }
}

function buildJacketKcsFormEditor(roll, jacketKcsForm) {
    const today = new Date().toISOString().slice(0, 10);
    return `
    <div class="order-info">
        <div class="order-title">
            <h2>📝 NHẬP PHIẾU KCS BỌC VỎ</h2>
            <span>${escapeHtml(roll.roll_code || "")}</span>
        </div>
        <div class="order-grid">
            <div><b>Roll</b><br>${escapeHtml(roll.roll_code || "—")}</div>
            <div><b>Loại</b><br>${escapeHtml(productLabel(roll.product_type))}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(roll.status || "—")}</div>
        </div>
    </div>
    <form onsubmit="submitJacketKcsForm(event, ${roll.id})">
        <div class="form-grid" style="margin-top:20px;">
            <div class="input-group">
                <label>STT</label>
                <input type="number" name="stt" value="${escapeHtml(jacketKcsForm.stt || "")}">
            </div>
            <div class="input-group">
                <label>Mã cuộn cáp</label>
                <input name="cable_code" value="${escapeHtml(jacketKcsForm.cable_code || "")}">
            </div>
            <div class="input-group">
                <label>Mã lõi</label>
                <input name="core_code" value="${escapeHtml(jacketKcsForm.core_code || "")}">
            </div>
            <div class="input-group">
                <label>Thông tin vỏ cáp</label>
                <input name="product_label" value="${escapeHtml(jacketKcsForm.product_label || "")}">
            </div>
            <div class="input-group">
                <label>Chiều dài (m)</label>
                <input type="number" step="0.01" name="length" value="${escapeHtml(jacketKcsForm.length || "")}">
            </div>
            <div class="input-group">
                <label>Loại sản phẩm</label>
                <input name="product_type" value="${escapeHtml(jacketKcsForm.product_type || "")}">
            </div>
            <div class="input-group">
                <label>Mã lô lỗi</label>
                <input name="error_roll_code" value="${escapeHtml(jacketKcsForm.error_roll_code || "")}">
            </div>
            <div class="input-group">
                <label>Ngày kiểm</label>
                <input type="date" name="manufacture_date" value="${escapeHtml(jacketKcsForm.manufacture_date || today)}">
            </div>
            <div class="input-group">
                <label>Kết quả KCS</label>
                <input name="inspection_result" value="${escapeHtml(jacketKcsForm.inspection_result || "")}">
            </div>
            <div class="input-group" style="grid-column: span 2;">
                <label>Ghi chú KCS</label>
                <input name="inspection_notes" value="${escapeHtml(jacketKcsForm.inspection_notes || "")}">
            </div>
            <div class="input-group">
                <label>BL1</label>
                <input name="bl1" value="${escapeHtml(jacketKcsForm.bl1 || "")}">
            </div>
            <div class="input-group">
                <label>Chiều đầu (m)</label>
                <input type="number" step="0.01" name="head_length" value="${escapeHtml(jacketKcsForm.head_length || "")}">
            </div>
            <div class="input-group">
                <label>Chiều đuôi (m)</label>
                <input type="number" step="0.01" name="tail_length" value="${escapeHtml(jacketKcsForm.tail_length || "")}">
            </div>
        </div>
        <div class="input-group" style="margin-top:10px;">
            <label>Ghi chú</label>
            <textarea name="notes" rows="4">${escapeHtml(jacketKcsForm.notes || "")}</textarea>
        </div>
        <button type="submit" class="btn btn-primary" style="margin-top:20px;">Lưu phiếu</button>
    </form>`;
}

async function submitSzForm(event, rollId) {
    event.preventDefault();
    const form = event.target;
    const payload = {
        stt: form.stt.value ? Number(form.stt.value) : null,
        product_code: form.product_code.value.trim() || null,
        core_code: form.core_code.value.trim() || null,
        shift: form.shift.value.trim() || null,
        production_date: form.production_date.value || null,
        machine: form.machine.value.trim() || null,
        machine_speed: form.machine_speed.value ? Number(form.machine_speed.value) : null,
        length: form.length.value ? Number(form.length.value) : null,
        sz_pitch: form.sz_pitch.value.trim() || null,
        lay_direction: form.lay_direction.value.trim() || null,
        tension: form.tension.value.trim() || null,
        pull_speed: form.pull_speed.value ? Number(form.pull_speed.value) : null,
        post_braid_diameter: form.post_braid_diameter.value ? Number(form.post_braid_diameter.value) : null,
        kcs_diameter: form.kcs_diameter.value ? Number(form.kcs_diameter.value) : null,
        kcs_uniformity: form.kcs_uniformity.value.trim() || null,
        kcs_external_inspection: form.kcs_external_inspection.value.trim() || null,
        kcs_notes: form.kcs_notes.value.trim() || null,
        notes: form.notes.value.trim() || null,
    };

    try {
        const response = await fetch(`${API_URL}/rolls/${rollId}/sz-form`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (response.ok) {
            alert(result.message || "Đã lưu phiếu thông tin Bện SZ.");
            showRollDetail(rollId);
            renderRolls(currentTab);
        } else {
            alert(result.detail || "Lưu phiếu thất bại.");
        }
    } catch (err) {
        alert("Không thể kết nối máy chủ.");
    }
}

async function submitJacketForm(event, rollId) {
    event.preventDefault();
    const form = event.target;
    const payload = {
        stt: form.stt.value ? Number(form.stt.value) : null,
        cable_code: form.cable_code.value.trim() || null,
        core_code: form.core_code.value.trim() || null,
            product_label: form.product_label.value.trim() || null,
        frp: form.frp.value.trim() || null,
        bl1: form.bl1.value.trim() || null,
        head_length: form.head_length.value ? Number(form.head_length.value) : null,
        tail_length: form.tail_length.value ? Number(form.tail_length.value) : null,
        measured_length: form.measured_length.value ? Number(form.measured_length.value) : null,
        loss_result: form.loss_result.value.trim() || null,
        measured_by: form.measured_by.value.trim() || null,
        notes: form.notes.value.trim() || null,
        kcs_measurements: collectJacketKcsMeasurements(form),
    };

    try {
        const response = await fetch(`${API_URL}/rolls/${rollId}/jacket-form`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (response.ok) {
            alert(result.message || "Đã lưu phiếu thông tin Bọc vỏ.");
            showRollDetail(rollId);
            renderRolls(currentTab);
        } else {
            alert(result.detail || "Lưu phiếu thất bại.");
        }
    } catch (err) {
        alert("Không thể kết nối máy chủ.");
    }
}

function collectJacketKcsMeasurements(form) {
    const colors = ["Dương", "Cam", "Lục", "Nâu", "Xám", "Trắng"];
    const result = {};
    colors.forEach(color => {
        const group = [];
        for (let i = 0; i < 12; i++) {
            group.push({
                loss_1310: form[`kcs_${color}_1310_${i}`]?.value ? Number(form[`kcs_${color}_1310_${i}`].value) : null,
                loss_1550: form[`kcs_${color}_1550_${i}`]?.value ? Number(form[`kcs_${color}_1550_${i}`].value) : null,
            });
        }
        result[color] = group;
    });
    return result;
}

async function submitJacketKcsForm(event, rollId) {
    event.preventDefault();
    const form = event.target;
    const payload = {
        stt: form.stt.value ? Number(form.stt.value) : null,
        cable_code: form.cable_code.value.trim() || null,
        core_code: form.core_code.value.trim() || null,
        product_label: form.product_label.value.trim() || null,
        length: form.length.value ? Number(form.length.value) : null,
        product_type: form.product_type.value.trim() || null,
        error_roll_code: form.error_roll_code.value.trim() || null,
        manufacture_date: form.manufacture_date.value || null,
        inspection_result: form.inspection_result.value.trim() || null,
        inspection_notes: form.inspection_notes.value.trim() || null,
        bl1: form.bl1.value.trim() || null,
        head_length: form.head_length.value ? Number(form.head_length.value) : null,
        tail_length: form.tail_length.value ? Number(form.tail_length.value) : null,
        notes: form.notes.value.trim() || null,
    };

    try {
        const response = await fetch(`${API_URL}/rolls/${rollId}/jacket-kcs-form`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (response.ok) {
            alert(result.message || "Đã lưu phiếu thông tin KCS Bọc vỏ.");
            showRollDetail(rollId);
            renderRolls(currentTab);
        } else {
            alert(result.detail || "Lưu phiếu thất bại.");
        }
    } catch (err) {
        alert("Không thể kết nối máy chủ.");
    }
}

async function submitLooseTubeForm(event, rollId) {
    event.preventDefault();
    const form = event.target;
    const payload = {
        stt: form.stt.value ? Number(form.stt.value) : null,
        fiber_code: form.fiber_code.value.trim() || null,
        shift: form.shift.value.trim() || null,
        tube_code: form.tube_code.value.trim() || null,
        machine_speed: form.machine_speed.value ? Number(form.machine_speed.value) : null,
        color: form.color.value.trim() || null,
        fiber_count: form.fiber_count.value ? Number(form.fiber_count.value) : null,
        diameter: form.diameter.value ? Number(form.diameter.value) : null,
        length: form.length.value ? Number(form.length.value) : null,
        production_date: form.production_date.value || null,
        bobbin_count: form.bobbin_count.value ? Number(form.bobbin_count.value) : null,
        notes: form.notes.value.trim() || null,
    };

    try {
        const response = await fetch(`${API_URL}/rolls/${rollId}/loose-tube-form`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (response.ok) {
            alert(result.message || "Đã lưu phiếu thông tin ống lỏng.");
            showRollDetail(rollId);
            renderRolls(currentTab);
        } else {
            alert(result.detail || "Lưu phiếu thất bại.");
        }
    } catch (err) {
        alert("Không thể kết nối máy chủ.");
    }
}

async function showFormDetail(formId) {
    const modalBody = document.getElementById("detailBody");
    const formType = selectedFormType();
    const config = FORM_TYPE_CONFIG[formType] || FORM_TYPE_CONFIG.loose_tube;

    modalBody.innerHTML = `<p style="text-align:center;">Đang tải chi tiết phiếu...</p>`;
    document.getElementById("detailModal").style.display = "flex";

    try {
        const response = await fetch(`${API_URL}${config.detailEndpoint}/${formId}`, {
            headers: { "Authorization": `Bearer ${authToken}` }
        });
        const form = await response.json();
        if (!response.ok) {
            modalBody.innerHTML = `<p style="color:var(--error)">${form.detail || "Không tải được chi tiết."}</p>`;
            return;
        }
        modalBody.innerHTML = config.detailBuilder(form);
    } catch (err) {
        modalBody.innerHTML = `<p style="color:var(--error)">Không thể kết nối máy chủ.</p>`;
    }
}

function buildLooseTubeFormDetailHtml(form) {
    return `
    <div class="order-info">
        <div class="order-title">
            <h2>📄 CHI TIẾT PHIẾU ỐNG LỎNG</h2>
            <span>Roll: ${escapeHtml(form.roll_code || "—")}</span>
        </div>
        <div class="order-grid">
            <div><b>Contract</b><br>${escapeHtml(form.contract_code || "—")}</div>
            <div><b>Khách hàng</b><br>${escapeHtml(form.customer_name || "—")}</div>
            <div><b>Người khai</b><br>${escapeHtml(form.operator_name || "—")}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(form.form_status || "—")}</div>
            <div><b>Ngày tạo</b><br>${escapeHtml(form.created_at || "—")}</div>
            <div><b>Cập nhật</b><br>${escapeHtml(form.updated_at || "—")}</div>
        </div>
    </div>
    <div class="order-info" style="margin-top:20px;">
        <div class="order-grid">
            <div><b>STT</b><br>${escapeHtml(form.stt || "—")}</div>
            <div><b>Mã sợi</b><br>${escapeHtml(form.fiber_code || "—")}</div>
            <div><b>Ca SX</b><br>${escapeHtml(form.shift || "—")}</div>
            <div><b>Mã ống</b><br>${escapeHtml(form.tube_code || "—")}</div>
            <div><b>Tốc độ máy</b><br>${form.machine_speed != null ? form.machine_speed + " m/min" : "—"}</div>
            <div><b>Màu</b><br>${escapeHtml(form.color || "—")}</div>
            <div><b>Số sợi</b><br>${escapeHtml(form.fiber_count || "—")}</div>
            <div><b>Đường kính</b><br>${form.diameter != null ? form.diameter + " mm" : "—"}</div>
            <div><b>Chiều dài</b><br>${form.length != null ? form.length + " m" : "—"}</div>
            <div><b>Ngày SX</b><br>${escapeHtml(form.production_date || "—")}</div>
            <div><b>Bobbin</b><br>${escapeHtml(form.bobbin_count || "—")}</div>
            <div style="grid-column: span 3;"><b>Ghi chú</b><br>${escapeHtml(form.notes || "—")}</div>
        </div>
    </div>`;
}

function buildSzFormDetailHtml(form) {
    return `
    <div class="order-info">
        <div class="order-title">
            <h2>📄 CHI TIẾT PHIẾU BỆN SZ</h2>
            <span>Roll: ${escapeHtml(form.roll_code || "—")}</span>
        </div>
        <div class="order-grid">
            <div><b>Contract</b><br>${escapeHtml(form.contract_code || "—")}</div>
            <div><b>Khách hàng</b><br>${escapeHtml(form.customer_name || "—")}</div>
            <div><b>Người khai</b><br>${escapeHtml(form.operator_name || "—")}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(form.form_status || "—")}</div>
            <div><b>Ngày tạo</b><br>${escapeHtml(form.created_at || "—")}</div>
            <div><b>Cập nhật</b><br>${escapeHtml(form.updated_at || "—")}</div>
        </div>
    </div>
    <div class="order-info" style="margin-top:20px;">
        <div class="order-grid">
            <div><b>STT</b><br>${escapeHtml(form.stt || "—")}</div>
            <div><b>Mã lõi</b><br>${escapeHtml(form.core_code || "—")}</div>
            <div><b>Ca SX</b><br>${escapeHtml(form.shift || "—")}</div>
            <div><b>Chiều dài</b><br>${form.length != null ? form.length + " m" : "—"}</div>
            <div><b>Ống Dương</b><br>${escapeHtml(form.tube_duong || "—")}</div>
            <div><b>Ống Cam</b><br>${escapeHtml(form.tube_cam || "—")}</div>
            <div><b>Ống Lục</b><br>${escapeHtml(form.tube_luc || "—")}</div>
            <div><b>Ống Nâu</b><br>${escapeHtml(form.tube_nau || "—")}</div>
            <div><b>Filler</b><br>${escapeHtml(form.filler || "—")}</div>
            <div><b>Ngày SX</b><br>${escapeHtml(form.production_date || "—")}</div>
            <div><b>Người nhập</b><br>${escapeHtml(form.operator_name || "—")}</div>
            <div style="grid-column: span 3;"><b>Ghi chú</b><br>${escapeHtml(form.notes || "—")}</div>
        </div>
    </div>`;
}

function buildJacketFormDetailHtml(form) {
    return `
    <div class="order-info">
        <div class="order-title">
            <h2>📄 CHI TIẾT PHIẾU BỌC VỎ</h2>
            <span>Roll: ${escapeHtml(form.roll_code || "—")}</span>
        </div>
        <div class="order-grid">
            <div><b>Contract</b><br>${escapeHtml(form.contract_code || "—")}</div>
            <div><b>Khách hàng</b><br>${escapeHtml(form.customer_name || "—")}</div>
            <div><b>Người khai</b><br>${escapeHtml(form.operator_name || "—")}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(form.form_status || "—")}</div>
            <div><b>Ngày tạo</b><br>${escapeHtml(form.created_at || "—")}</div>
            <div><b>Cập nhật</b><br>${escapeHtml(form.updated_at || "—")}</div>
        </div>
    </div>
    <div class="order-info" style="margin-top:20px;">
        <div class="order-grid">
            <div><b>STT</b><br>${escapeHtml(form.stt || "—")}</div>
            <div><b>Mã cuộn</b><br>${escapeHtml(form.cable_code || "—")}</div>
            <div><b>Mã lõi</b><br>${escapeHtml(form.core_code || "—")}</div>
            <div><b>Thông tin vỏ cáp</b><br>${escapeHtml(form.product_label || "—")}</div>
            <div><b>Chiều dài</b><br>${form.length != null ? form.length + " m" : "—"}</div>
            <div><b>Loại sản phẩm</b><br>${escapeHtml(form.product_type || "—")}</div>
            <div><b>Mã lô lỗi</b><br>${escapeHtml(form.error_roll_code || "—")}</div>
            <div><b>Ngày SX</b><br>${escapeHtml(form.manufacture_date || "—")}</div>
            <div><b>BL1</b><br>${escapeHtml(form.bl1 || "—")}</div>
            <div><b>Chiều đầu</b><br>${form.head_length != null ? form.head_length + " m" : "—"}</div>
            <div><b>Chiều đuôi</b><br>${form.tail_length != null ? form.tail_length + " m" : "—"}</div>
            <div><b>Người nhập</b><br>${escapeHtml(form.operator_name || "—")}</div>
            <div style="grid-column: span 3;"><b>Ghi chú</b><br>${escapeHtml(form.notes || "—")}</div>
        </div>
    </div>`;
}

function buildJacketKcsFormDetailHtml(form) {
    return `
    <div class="order-info">
        <div class="order-title">
            <h2>📄 CHI TIẾT PHIẾU KCS BỌC VỎ</h2>
            <span>Roll: ${escapeHtml(form.roll_code || "—")}</span>
        </div>
        <div class="order-grid">
            <div><b>Contract</b><br>${escapeHtml(form.contract_code || "—")}</div>
            <div><b>Khách hàng</b><br>${escapeHtml(form.customer_name || "—")}</div>
            <div><b>Người khai</b><br>${escapeHtml(form.operator_name || "—")}</div>
            <div><b>Trạng thái</b><br>${escapeHtml(form.form_status || "—")}</div>
            <div><b>Ngày tạo</b><br>${escapeHtml(form.created_at || "—")}</div>
            <div><b>Cập nhật</b><br>${escapeHtml(form.updated_at || "—")}</div>
        </div>
    </div>
    <div class="order-info" style="margin-top:20px;">
        <div class="order-grid">
            <div><b>STT</b><br>${escapeHtml(form.stt || "—")}</div>
            <div><b>Mã cuộn</b><br>${escapeHtml(form.cable_code || "—")}</div>
            <div><b>Mã lõi</b><br>${escapeHtml(form.core_code || "—")}</div>
            <div><b>Thông tin vỏ cáp</b><br>${escapeHtml(form.product_label || "—")}</div>
            <div><b>Chiều dài</b><br>${form.length != null ? form.length + " m" : "—"}</div>
            <div><b>Loại sản phẩm</b><br>${escapeHtml(form.product_type || "—")}</div>
            <div><b>Mã lô lỗi</b><br>${escapeHtml(form.error_roll_code || "—")}</div>
            <div><b>Ngày SX</b><br>${escapeHtml(form.manufacture_date || "—")}</div>
            <div><b>Kết quả KCS</b><br>${escapeHtml(form.inspection_result || "—")}</div>
            <div style="grid-column: span 3;"><b>Ghi chú KCS</b><br>${escapeHtml(form.inspection_notes || "—")}</div>
            <div><b>Người nhập</b><br>${escapeHtml(form.operator_name || "—")}</div>
            <div style="grid-column: span 3;"><b>Ghi chú</b><br>${escapeHtml(form.notes || "—")}</div>
        </div>
    </div>`;
}

async function showAuditLog(role = "all") {
    const modalBody = document.getElementById("detailBody");
    modalBody.innerHTML = `<p style="text-align:center;">Đang tải nhật ký...</p>`;
    document.getElementById("detailModal").style.display = "flex";

    try {
        const response = await fetch(`${API_URL}/audit-logs?role=${encodeURIComponent(role)}`, {
            headers: { "Authorization": `Bearer ${authToken}` }
        });
        const logs = await response.json();

        if (!response.ok) {
            modalBody.innerHTML = `<p style="color:var(--error)">${logs.detail || "Không tải được nhật ký."}</p>`;
            return;
        }

        modalBody.innerHTML = buildAuditLogHtml(logs, role);
    } catch (err) {
        modalBody.innerHTML = `<p style="color:var(--error)">Không thể kết nối máy chủ.</p>`;
    }
}

function buildAuditLogHtml(logs, currentRole) {
    const roleOptions = ["all", "admin", "worker1", "worker2", "worker3", "inspector"]
        .map(r => `<option value="${r}" ${r === currentRole ? "selected" : ""}>${r === "all" ? "Tất cả vai trò" : (ROLE_LABELS[r] || r)}</option>`)
        .join("");

    const rows = logs.length > 0
        ? logs.map(l => `
            <tr>
                <td>${l.created_at || ""}</td>
                <td>${l.username || "—"}</td>
                <td><span class="status-badge stage-badge">${ROLE_LABELS[l.role] || l.role || "—"}</span></td>
                <td>${ACTION_LABELS[l.action] || l.action}</td>
                <td>${l.target || ""}</td>
                <td>${l.description || ""}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">Chưa có nhật ký nào.</td></tr>`;

    return `
        <div class="order-info">
            <div class="order-title"><h2>📜 NHẬT KÝ THAO TÁC HỆ THỐNG</h2></div>
        </div>
        <div style="margin:15px 0;">
            <label style="margin-right:10px; font-weight:600;">Lọc theo vai trò:</label>
            <select id="audit-role-filter" class="modern-select" style="width:auto; display:inline-block;">
                ${roleOptions}
            </select>
        </div>
        <div class="table-container">
            <table class="detail-table">
                <thead>
                    <tr><th>Thời gian</th><th>Người dùng</th><th>Vai trò</th><th>Hành động</th><th>Đối tượng</th><th>Chi tiết</th></tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}

// Ủy quyền sự kiện: chọn lại bộ lọc vai trò sẽ tải lại nhật ký ngay trong modal
document.getElementById("detailBody").addEventListener("change", (e) => {
    if (e.target && e.target.id === "audit-role-filter") {
        showAuditLog(e.target.value);
    }
});

// =========================================================
// 8. ĐĂNG XUẤT
// =========================================================
document.getElementById("logout-btn").addEventListener("click", (e) => {
    e.preventDefault();

    authToken = null;
    currentUsername = null;
    rollCache = {};

    const loginForm = document.getElementById("login-form");
    if (loginForm) loginForm.reset();

    dashboardScreen.classList.add("hidden");
    loginScreen.classList.remove("hidden");

    document.getElementById("user-display").textContent = "";
    document.getElementById("role-display").textContent = "";
    if (adminNav) adminNav.classList.add("hidden");

    window.location.href = window.location.pathname;
});

// =========================================================
// 9. ĐÓNG MODAL CHI TIẾT
// =========================================================
document.getElementById("detailModal").addEventListener("click", (e) => {
    if (e.target.id === "detailModal") {
        document.getElementById("detailModal").style.display = "none";
    }
});

// =========================================================
// 10. ĐỔI MẬT KHẨU
// =========================================================
const togglePwdBtn = document.getElementById("toggle-pwd-btn");
const passwordFormContainer = document.getElementById("password-form-container");

togglePwdBtn.addEventListener("click", () => {
    passwordFormContainer.classList.toggle("hidden-fields");
});

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

    try {
        const response = await fetch(`${API_URL}/change-password`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`
            },
            body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
        });

        const result = await response.json();

        if (response.ok) {
            msg.style.color = "#22c55e";
            msg.textContent = result.message;
            document.getElementById("change-pwd-form").reset();
        } else {
            msg.style.color = "#ef4444";
            msg.textContent = result.detail;
        }
    } catch (err) {
        msg.style.color = "#ef4444";
        msg.textContent = "Không kết nối được máy chủ.";
    }
});
