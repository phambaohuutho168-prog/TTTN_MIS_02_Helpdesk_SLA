"use strict";

const API_PREFIX = "/api/v1";

const STORAGE_KEYS = Object.freeze({
    accessToken: "helpdesk.dashboard.accessToken",
    refreshToken: "helpdesk.dashboard.refreshToken",
    user: "helpdesk.dashboard.user",
});

const adminState = {
    user: null,
    roles: [],
    departments: [],
    page: 1,
    pageSize: 20,
    totalPages: 0,
    loading: false,
    editingUser: null,
};

const elements = {};

document.addEventListener("DOMContentLoaded", initializeAdminPage);

function initializeAdminPage() {
    cacheAdminElements();

    elements.logoutButton.addEventListener("click", handleAdminLogout);
    elements.filterForm.addEventListener("submit",handleUserFilter,);
    elements.filterReset.addEventListener("click",resetUserFilters,);
    elements.pagePrevious.addEventListener("click",showPreviousUserPage,);
    elements.pageNext.addEventListener("click",showNextUserPage,);
    elements.createToggle.addEventListener("click",toggleCreatePanel,);
    elements.createCancel.addEventListener("click",closeCreatePanel,);
    elements.createForm.addEventListener("submit",handleCreateUser,);
    elements.editDialog = document.getElementById("user-edit-dialog",);
    elements.editClose = document.getElementById("user-edit-close",);
    elements.editLoading = document.getElementById("user-edit-loading",);
    elements.editError = document.getElementById("user-edit-error",);
    elements.editForm = document.getElementById("user-edit-form",);
    elements.editTitle = document.getElementById("user-edit-title",);
    elements.editEmail = document.getElementById("user-edit-email",);
    elements.editFullName = document.getElementById("user-edit-full-name",);
    elements.editPhone = document.getElementById("user-edit-phone",);
    elements.editDepartment = document.getElementById("user-edit-department",);
    elements.editRoles = document.getElementById("user-edit-roles",);
    elements.editIsActive = document.getElementById("user-edit-is-active",);
    elements.editMeta = document.getElementById("user-edit-meta",);
    elements.editSubmit = document.getElementById("user-edit-submit",);
    elements.editClose.addEventListener("click",closeUserEdit,);
    elements.editDialog.addEventListener("click",handleUserEditBackdrop,);
    elements.editForm.addEventListener("submit",handleEditUser,);

    const accessToken = sessionStorage.getItem(
        STORAGE_KEYS.accessToken,
    );
    adminState.user = readStoredUser();

    if (!accessToken || !adminState.user) {
        window.location.replace("/portal");
        return;
    }

    showSessionInformation();

    if (!hasAdminRole(adminState.user)) {
        showAccessDenied();
        return;
    }

    showAdminWorkspace();
    startAdminWorkspace();
}

function cacheAdminElements() {
    elements.loading = document.getElementById("admin-loading");
    elements.denied = document.getElementById("admin-denied");
    elements.shell = document.getElementById("admin-shell");

    elements.sessionNavigation = document.getElementById("admin-session-navigation",);
    elements.currentUserName = document.getElementById("admin-current-user-name",);
    elements.currentUserRole = document.getElementById("admin-current-user-role",);
    elements.logoutButton = document.getElementById("admin-logout-button",);

    elements.createToggle = document.getElementById("user-create-toggle",);
    elements.createPanel = document.getElementById("user-create-panel",);
    elements.createForm = document.getElementById("user-create-form",);
    elements.createError = document.getElementById("user-create-error",);
    elements.createFullName = document.getElementById("user-create-full-name",);
    elements.createEmail = document.getElementById("user-create-email",);
    elements.createPassword = document.getElementById("user-create-password",);
    elements.createPhone = document.getElementById("user-create-phone",);
    elements.createDepartment = document.getElementById("user-create-department",);
    elements.createRoles = document.getElementById("user-create-roles",);
    elements.createIsActive = document.getElementById("user-create-is-active",);
    elements.createSubmit = document.getElementById("user-create-submit",);
    elements.createCancel = document.getElementById("user-create-cancel",);
    elements.listSummary = document.getElementById("user-list-summary",);
    elements.message = document.getElementById("admin-message");

    elements.totalUsers = document.getElementById("admin-total-users",);
    elements.activeUsers = document.getElementById("admin-active-users",);
    elements.inactiveUsers = document.getElementById("admin-inactive-users",);

    elements.filterForm = document.getElementById("user-filter-form",);
    elements.filterQuery = document.getElementById("user-filter-query",);
    elements.filterRole = document.getElementById("user-filter-role",);
    elements.filterDepartment = document.getElementById("user-filter-department",);
    elements.filterStatus = document.getElementById("user-filter-status",);
    elements.filterSubmit = document.getElementById("user-filter-submit",);
    elements.filterReset = document.getElementById("user-filter-reset",);

    elements.listLoading = document.getElementById("user-list-loading",);
    elements.listError = document.getElementById("user-list-error",);
    elements.listEmpty = document.getElementById("user-list-empty",);
    elements.tableWrapper = document.getElementById("user-table-wrapper",);
    elements.tableBody = document.getElementById("user-table-body",);

    elements.pagination = document.getElementById("user-pagination",);
    elements.pagePrevious = document.getElementById("user-page-previous",);
    elements.pageNext = document.getElementById("user-page-next",);
    elements.pageInformation = document.getElementById("user-page-information",);
    }

function readStoredUser() {
    const value = sessionStorage.getItem(STORAGE_KEYS.user);

    if (!value) return null;

    try {
        return JSON.parse(value);
    } catch (_error) {
        clearStoredSession();
        return null;
    }
}

function hasAdminRole(user) {
    return (user.roles || []).some(
        (role) => role.role_code === "ADMIN",
    );
}

function showSessionInformation() {
    elements.currentUserName.textContent =
        adminState.user.full_name || adminState.user.email;
    elements.currentUserRole.textContent = hasAdminRole(adminState.user)
        ? "Quản trị viên"
        : "Người dùng";
    elements.sessionNavigation.hidden = false;
}

function showAccessDenied() {
    elements.loading.hidden = true;
    elements.shell.hidden = true;
    elements.denied.hidden = false;
}

function showAdminWorkspace() {
    elements.loading.hidden = true;
    elements.denied.hidden = true;
    elements.shell.hidden = false;

    elements.createToggle.disabled = false;
    elements.createToggle.removeAttribute("title");
    elements.listSummary.textContent =
        "Đang chuẩn bị dữ liệu quản trị...";
}

async function startAdminWorkspace() {
    try {
        await loadAdminCatalogs();

        await Promise.all([
            loadAdminSummary(),
            loadUsers(),
        ]);
    } catch (error) {
        showListError(error.message);
    }
}

async function loadAdminCatalogs() {
    const [roles, departments] = await Promise.all([
        apiRequest("/admin/roles"),
        apiRequest("/admin/departments"),
    ]);

    adminState.roles = roles || [];
    adminState.departments = departments || [];

    populateSelect(
        elements.filterRole,
        adminState.roles,
        "role_code",
        "role_name",
        "Tất cả vai trò",
    );

    populateSelect(
        elements.filterDepartment,
        adminState.departments,
        "department_id",
        "department_name",
        "Tất cả phòng ban",
    );
}

function populateSelect(
    select,
    items,
    valueKey,
    labelKey,
    placeholder,
) {
    select.replaceChildren();

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = placeholder;
    select.append(defaultOption);

    for (const item of items || []) {
        const option = document.createElement("option");

        option.value = String(item[valueKey]);
        option.textContent = item[labelKey];

        select.append(option);
    }
}
populateSelect(
    elements.createDepartment,
    adminState.departments,
    "department_id",
    "department_name",
    "Không chọn phòng ban",
);

renderRoleCheckboxes(elements.createRoles);

async function loadAdminSummary() {
    const [allUsers, activeUsers, inactiveUsers] =
        await Promise.all([
            apiRequest("/admin/users?page=1&page_size=1"),
            apiRequest(
                "/admin/users?page=1&page_size=1&is_active=true",
            ),
            apiRequest(
                "/admin/users?page=1&page_size=1&is_active=false",
            ),
        ]);

    elements.totalUsers.textContent = formatNumber(
        allUsers.total,
    );
    elements.activeUsers.textContent = formatNumber(
        activeUsers.total,
    );
    elements.inactiveUsers.textContent = formatNumber(
        inactiveUsers.total,
    );
}

function buildUserQuery() {
    const query = new URLSearchParams({
        page: String(adminState.page),
        page_size: String(adminState.pageSize),
    });

    const search = elements.filterQuery.value.trim();

    if (search) {
        query.set("q", search);
    }

    if (elements.filterRole.value) {
        query.set("role_code", elements.filterRole.value);
    }

    if (elements.filterDepartment.value) {
        query.set(
            "department_id",
            elements.filterDepartment.value,
        );
    }

    if (elements.filterStatus.value) {
        query.set("is_active", elements.filterStatus.value);
    }

    return query.toString();
}

async function loadUsers() {
    if (adminState.loading) return;

    setListBusy(true);
    clearListError();

    try {
        const data = await apiRequest(
            `/admin/users?${buildUserQuery()}`,
        );

        renderUserList(data);
    } catch (error) {
        showListError(error.message);
    } finally {
        setListBusy(false);
    }
}

function renderUserList(data) {
    adminState.page = data.page;
    adminState.totalPages = data.total_pages;

    elements.tableBody.replaceChildren();

    elements.listSummary.textContent =
        `${formatNumber(data.total)} tài khoản phù hợp`;

    const users = data.items || [];
    const hasUsers = users.length > 0;

    elements.listEmpty.hidden = hasUsers;
    elements.tableWrapper.hidden = !hasUsers;
    elements.pagination.hidden = !hasUsers;

    for (const user of users) {
        elements.tableBody.append(createUserRow(user));
    }

    const displayedTotalPages = Math.max(
        data.total_pages,
        1,
    );

    elements.pageInformation.textContent =
        `Trang ${data.page}/${displayedTotalPages}`;

    elements.pagePrevious.disabled = data.page <= 1;
    elements.pageNext.disabled =
        data.total_pages === 0 ||
        data.page >= data.total_pages;
}

function createUserRow(user) {
    const row = document.createElement("tr");

    row.append(
        createIdentityCell(user),
        createTextCell(
            user.department?.department_name || "Chưa phân phòng ban",
            "Phòng ban",
        ),
        createRoleCell(user.roles),
        createStatusCell(user.is_active),
        createTextCell(
            formatDateTime(user.created_at),
            "Ngày tạo",
        ),
        createActionCell(user),
    );

    return row;
}

function createIdentityCell(user) {
    const cell = document.createElement("td");
    const wrapper = document.createElement("div");
    const name = document.createElement("strong");
    const email = document.createElement("span");

    cell.dataset.label = "Tài khoản";
    wrapper.className = "admin-user-identity";

    name.textContent = user.full_name;
    email.textContent = user.email;

    wrapper.append(name, email);
    cell.append(wrapper);

    return cell;
}

function createRoleCell(roles) {
    const cell = document.createElement("td");
    const wrapper = document.createElement("div");

    cell.dataset.label = "Vai trò";
    wrapper.className = "admin-role-list";

    for (const role of roles || []) {
        const badge = document.createElement("span");

        badge.className = "admin-role-badge";
        badge.textContent = role.role_name || role.role_code;

        wrapper.append(badge);
    }

    if (!wrapper.childElementCount) {
        wrapper.textContent = "Chưa có vai trò";
    }

    cell.append(wrapper);

    return cell;
}

function createStatusCell(isActive) {
    const cell = document.createElement("td");
    const badge = document.createElement("span");

    cell.dataset.label = "Trạng thái";
    badge.className =
        "admin-account-status " +
        (
            isActive
                ? "admin-account-status--active"
                : "admin-account-status--inactive"
        );
    badge.textContent = isActive
        ? "Đang hoạt động"
        : "Đã khóa";

    cell.append(badge);

    return cell;
}

function createActionCell(user) {
    const cell = document.createElement("td");
    const button = document.createElement("button");

    cell.dataset.label = "Thao tác";

    button.type = "button";
    button.className = "admin-action-button";
    button.textContent = "Chỉnh sửa";
    button.addEventListener("click", () => {
        openUserEdit(user.user_id);
    });

    cell.append(button);

    return cell;
}

function createTextCell(value, label) {
    const cell = document.createElement("td");

    cell.dataset.label = label;
    cell.textContent = value;

    return cell;
}

async function handleUserFilter(event) {
    event.preventDefault();
    adminState.page = 1;

    await loadUsers();
}

async function resetUserFilters() {
    elements.filterQuery.value = "";
    elements.filterRole.value = "";
    elements.filterDepartment.value = "";
    elements.filterStatus.value = "";

    adminState.page = 1;

    await loadUsers();
}

async function showPreviousUserPage() {
    if (adminState.page <= 1) return;

    adminState.page -= 1;

    await loadUsers();
}

async function showNextUserPage() {
    if (adminState.page >= adminState.totalPages) return;

    adminState.page += 1;

    await loadUsers();
}

function setListBusy(busy) {
    adminState.loading = busy;
    elements.listLoading.hidden = !busy;

    for (const control of elements.filterForm.elements) {
        control.disabled = busy;
    }

    elements.pagePrevious.disabled =
        busy || adminState.page <= 1;
    elements.pageNext.disabled =
        busy ||
        adminState.totalPages === 0 ||
        adminState.page >= adminState.totalPages;
}

function showListError(message) {
    elements.listError.textContent = message;
    elements.listError.hidden = false;
    elements.listLoading.hidden = true;
}

function clearListError() {
    elements.listError.textContent = "";
    elements.listError.hidden = true;
}

function formatDateTime(value) {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return "—";

    return new Intl.DateTimeFormat("vi-VN", {
        dateStyle: "short",
        timeStyle: "short",
    }).format(date);
}

function formatNumber(value) {
    return new Intl.NumberFormat("vi-VN").format(
        Number(value || 0),
    );
}

function renderRoleCheckboxes(container, selectedIds = new Set()) {
    container.replaceChildren();

    for (const role of adminState.roles) {
        if (!role.is_active) continue;

        const label = document.createElement("label");
        const input = document.createElement("input");
        const text = document.createElement("span");

        label.className = "role-checkbox";

        input.type = "checkbox";
        input.name = "user-role";
        input.value = String(role.role_id);
        input.checked = selectedIds.has(role.role_id);

        text.textContent = role.role_name;

        label.append(input, text);
        container.append(label);
    }
}

function selectedRoleIds(container) {
    return Array.from(
        container.querySelectorAll(
            'input[name="user-role"]:checked',
        ),
        (input) => Number(input.value),
    );
}

function toggleCreatePanel() {
    const shouldOpen = elements.createPanel.hidden;

    elements.createPanel.hidden = !shouldOpen;
    elements.createToggle.setAttribute(
        "aria-expanded",
        String(shouldOpen),
    );
    elements.createToggle.textContent = shouldOpen
        ? "Đóng biểu mẫu"
        : "Thêm tài khoản";

    if (shouldOpen) {
        window.setTimeout(
            () => elements.createFullName.focus(),
            0,
        );
    }
}

function closeCreatePanel() {
    elements.createPanel.hidden = true;
    elements.createToggle.setAttribute(
        "aria-expanded",
        "false",
    );
    elements.createToggle.textContent = "Thêm tài khoản";

    elements.createForm.reset();
    elements.createIsActive.checked = true;

    clearCreateError();

    populateSelect(
        elements.createDepartment,
        adminState.departments,
        "department_id",
        "department_name",
        "Không chọn phòng ban",
    );

    renderRoleCheckboxes(elements.createRoles);
}

async function handleCreateUser(event) {
    event.preventDefault();
    clearCreateError();

    const roleIds = selectedRoleIds(elements.createRoles);

    if (!roleIds.length) {
        showCreateError("Vui lòng chọn ít nhất một vai trò.");
        return;
    }

    const departmentValue = elements.createDepartment.value;
    const phone = elements.createPhone.value.trim();

    setCreateBusy(true);

    try {
        const user = await apiRequest("/admin/users", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                email: elements.createEmail.value.trim(),
                full_name: elements.createFullName.value.trim(),
                password: elements.createPassword.value,
                phone: phone || null,
                department_id: departmentValue
                    ? Number(departmentValue)
                    : null,
                role_ids: roleIds,
                is_active: elements.createIsActive.checked,
            }),
        });

        elements.message.textContent =
            `Đã tạo tài khoản ${user.email} thành công.`;
        elements.message.hidden = false;

        closeCreatePanel();

        adminState.page = 1;

        await Promise.all([
            loadAdminSummary(),
            loadUsers(),
        ]);
    } catch (error) {
        showCreateError(error.message);
    } finally {
        setCreateBusy(false);
    }
}

function setCreateBusy(busy) {
    for (const control of elements.createForm.elements) {
        control.disabled = busy;
    }

    elements.createToggle.disabled = busy;
    elements.createSubmit.textContent = busy
        ? "Đang tạo..."
        : "Tạo tài khoản";
}

function showCreateError(message) {
    elements.createError.textContent = message;
    elements.createError.hidden = false;
}

function clearCreateError() {
    elements.createError.textContent = "";
    elements.createError.hidden = true;
}

function resetUserEditDialog() {
    adminState.editingUser = null;

    elements.editLoading.hidden = false;
    elements.editError.textContent = "";
    elements.editError.hidden = true;
    elements.editForm.hidden = true;
    elements.editForm.reset();
}

async function openUserEdit(userId) {
    resetUserEditDialog();

    if (!elements.editDialog.open) {
        elements.editDialog.showModal();
    }

    try {
        const user = await apiRequest(
            `/admin/users/${userId}`,
        );

        adminState.editingUser = user;
        renderUserEdit(user);
    } catch (error) {
        elements.editLoading.hidden = true;
        showEditError(error.message);
    }
}

function renderUserEdit(user) {
    elements.editTitle.textContent = user.full_name;
    elements.editEmail.value = user.email;
    elements.editFullName.value = user.full_name;
    elements.editPhone.value = user.phone || "";

    populateSelect(
        elements.editDepartment,
        adminState.departments,
        "department_id",
        "department_name",
        "Không chọn phòng ban",
    );

    elements.editDepartment.value = user.department
        ? String(user.department.department_id)
        : "";

    renderRoleCheckboxes(
        elements.editRoles,
        new Set(
            (user.roles || []).map((role) => role.role_id),
        ),
    );

    elements.editIsActive.checked = user.is_active;
    elements.editMeta.textContent =
        `Tạo lúc ${formatDateTime(user.created_at)} · ` +
        `Cập nhật lúc ${formatDateTime(user.updated_at)}`;

    elements.editLoading.hidden = true;
    elements.editError.hidden = true;
    elements.editForm.hidden = false;

    protectCurrentAdminAccount();
}

function protectCurrentAdminAccount() {
    const editingUser = adminState.editingUser;
    const currentUserId = adminState.user?.user_id;

    if (!editingUser || editingUser.user_id !== currentUserId) {
        return;
    }

    elements.editIsActive.disabled = true;

    const adminRole = adminState.roles.find(
        (role) => role.role_code === "ADMIN",
    );

    if (!adminRole) return;

    const adminRoleInput = elements.editRoles.querySelector(
        `input[value="${adminRole.role_id}"]`,
    );

    if (adminRoleInput) {
        adminRoleInput.checked = true;
        adminRoleInput.disabled = true;
    }
}

function closeUserEdit() {
    if (elements.editDialog.open) {
        elements.editDialog.close();
    }

    adminState.editingUser = null;
}

function handleUserEditBackdrop(event) {
    if (event.target === elements.editDialog) {
        closeUserEdit();
    }
}

async function handleEditUser(event) {
    event.preventDefault();
    clearEditError();

    const user = adminState.editingUser;

    if (!user) {
        showEditError("Không xác định được tài khoản.");
        return;
    }

    const roleIds = selectedRoleIds(elements.editRoles);

    if (!roleIds.length) {
        showEditError("Tài khoản phải có ít nhất một vai trò.");
        return;
    }

    const phone = elements.editPhone.value.trim();
    const departmentValue = elements.editDepartment.value;

    setEditBusy(true);

    try {
        await apiRequest(`/admin/users/${user.user_id}`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                full_name: elements.editFullName.value.trim(),
                phone: phone || null,
                department_id: departmentValue
                    ? Number(departmentValue)
                    : null,
                is_active: elements.editIsActive.checked,
            }),
        });

        await synchronizeUserRoles(
            user.user_id,
            user.roles || [],
            roleIds,
        );

        const updatedUser = await apiRequest(
            `/admin/users/${user.user_id}`,
        );

        updateCurrentAdminSession(updatedUser);

        elements.message.textContent =
            `Đã cập nhật tài khoản ${updatedUser.email}.`;
        elements.message.hidden = false;

        closeUserEdit();

        await Promise.all([
            loadAdminSummary(),
            loadUsers(),
        ]);
    } catch (error) {
        showEditError(error.message);
    } finally {
        setEditBusy(false);
    }
}

async function synchronizeUserRoles(
    userId,
    existingRoles,
    selectedIds,
) {
    const existingIds = new Set(
        existingRoles.map((role) => role.role_id),
    );
    const selectedIdSet = new Set(selectedIds);

    for (const roleId of selectedIdSet) {
        if (existingIds.has(roleId)) continue;

        await apiRequest(
            `/admin/users/${userId}/roles/${roleId}`,
            {
                method: "PUT",
            },
        );
    }

    for (const roleId of existingIds) {
        if (selectedIdSet.has(roleId)) continue;

        await apiRequest(
            `/admin/users/${userId}/roles/${roleId}`,
            {
                method: "DELETE",
            },
        );
    }
}

function updateCurrentAdminSession(updatedUser) {
    if (
        updatedUser.user_id !== adminState.user?.user_id
    ) {
        return;
    }

    adminState.user = {
        ...adminState.user,
        full_name: updatedUser.full_name,
        phone: updatedUser.phone,
        department: updatedUser.department,
        roles: updatedUser.roles,
        is_active: updatedUser.is_active,
    };

    sessionStorage.setItem(
        STORAGE_KEYS.user,
        JSON.stringify(adminState.user),
    );

    showSessionInformation();
}

function setEditBusy(busy) {
    for (const control of elements.editForm.elements) {
        control.disabled = busy;
    }

    elements.editClose.disabled = busy;
    elements.editSubmit.textContent = busy
        ? "Đang lưu..."
        : "Lưu thay đổi";

    if (!busy) {
        protectCurrentAdminAccount();
    }
}

function showEditError(message) {
    elements.editError.textContent = message;
    elements.editError.hidden = false;
    elements.editLoading.hidden = true;
}

function clearEditError() {
    elements.editError.textContent = "";
    elements.editError.hidden = true;
}

async function handleAdminLogout() {
    const accessToken = sessionStorage.getItem(
        STORAGE_KEYS.accessToken,
    );
    const refreshToken = sessionStorage.getItem(
        STORAGE_KEYS.refreshToken,
    );

    try {
        if (accessToken && refreshToken) {
            await fetch(`${API_PREFIX}/auth/logout`, {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${accessToken}`,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                body: JSON.stringify({
                    refresh_token: refreshToken,
                }),
            });
        }
    } finally {
        clearStoredSession();
        window.location.replace("/portal");
    }
}

function clearStoredSession() {
    for (const key of Object.values(STORAGE_KEYS)) {
        sessionStorage.removeItem(key);
    }
}
async function apiRequest(path, options = {}, retry = true) {
    const headers = new Headers(options.headers || {});
    const accessToken = sessionStorage.getItem(
        STORAGE_KEYS.accessToken,
    );

    headers.set("Accept", "application/json");

    if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
    }

    let response;

    try {
        response = await fetch(`${API_PREFIX}${path}`, {
            ...options,
            headers,
        });
    } catch (_error) {
        throw new Error("Không thể kết nối đến máy chủ.");
    }

    if (response.status === 401 && retry) {
        const refreshed = await refreshAdminSession();

        if (refreshed) {
            return apiRequest(path, options, false);
        }
    }

    const payload = await parseResponse(response);

    if (!response.ok) {
        if (response.status === 401) {
            clearStoredSession();
            window.location.replace("/portal");
        }

        const requestError = new Error(
            errorMessage(
                payload,
                `Yêu cầu thất bại (${response.status}).`,
            ),
        );

        requestError.status = response.status;
        requestError.code = payload?.code || null;

        throw requestError;
    }

    return payload?.data;
}

async function refreshAdminSession() {
    const refreshToken = sessionStorage.getItem(
        STORAGE_KEYS.refreshToken,
    );

    if (!refreshToken) return false;

    try {
        const response = await fetch(`${API_PREFIX}/auth/refresh`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body: JSON.stringify({
                refresh_token: refreshToken,
            }),
        });

        const payload = await parseResponse(response);

        if (!response.ok || !payload?.data?.access_token) {
            clearStoredSession();
            return false;
        }

        sessionStorage.setItem(
            STORAGE_KEYS.accessToken,
            payload.data.access_token,
        );

        if (payload.data.refresh_token) {
            sessionStorage.setItem(
                STORAGE_KEYS.refreshToken,
                payload.data.refresh_token,
            );
        }

        if (payload.data.user) {
            adminState.user = payload.data.user;
            sessionStorage.setItem(
                STORAGE_KEYS.user,
                JSON.stringify(payload.data.user),
            );
            showSessionInformation();
        }

        return true;
    } catch (_error) {
        clearStoredSession();
        return false;
    }
}

async function parseResponse(response) {
    if (response.status === 204) return null;

    const contentType = response.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) return null;

    try {
        return await response.json();
    } catch (_error) {
        return null;
    }
}

function errorMessage(payload, fallback) {
    if (payload?.message && payload?.errors?.[0]?.message) {
        const field = payload.errors[0].field
            ? `${payload.errors[0].field}: `
            : "";

        return `${payload.message} ${field}${payload.errors[0].message}`;
    }

    if (payload?.message) return payload.message;
    if (typeof payload?.detail === "string") return payload.detail;

    return fallback;
}
