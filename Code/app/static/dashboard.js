"use strict";

const API_PREFIX = "/api/v1";
const STORAGE_KEYS = Object.freeze({
    accessToken: "helpdesk.dashboard.accessToken",
    refreshToken: "helpdesk.dashboard.refreshToken",
    user: "helpdesk.dashboard.user",
});

const STATUS_COLORS = Object.freeze({
    NEW: "#2670ed",
    ASSIGNED: "#7553d6",
    IN_PROGRESS: "#df7b24",
    WAITING_REQUESTER: "#d3a018",
    RESOLVED: "#16865c",
    CLOSED: "#273f68",
    REJECTED: "#bf2c3a",
    REOPENED: "#13858c",
});

const state = {
    accessToken: sessionStorage.getItem(STORAGE_KEYS.accessToken),
    refreshToken: sessionStorage.getItem(STORAGE_KEYS.refreshToken),
    user: readStoredUser(),
    loading: false,
    refreshPromise: null,
};

const elements = {};

document.addEventListener("DOMContentLoaded", initialize);

function initialize() {
    cacheElements();
    setDefaultDates();
    elements.loginForm.addEventListener("submit", handleLogin);
    elements.dashboardFilters.addEventListener("submit", handleFilterSubmit);
    elements.resetFilters.addEventListener("click", resetFilters);
    elements.logoutButton.addEventListener("click", handleLogout);
    elements.menuButton.addEventListener("click", toggleMobileNavigation);
    elements.deniedBackToLogin.addEventListener("click", () => showLogin());

    if (state.accessToken && state.user) {
        startDashboard();
    } else {
        showLogin();
    }
}

function cacheElements() {
    const ids = [
        "auth-panel", "login-form", "login-email", "login-password", "login-button",
        "login-error", "access-denied-state", "access-denied-message", "denied-back-to-login",
        "dashboard-shell", "dashboard-filters", "filter-from", "filter-to",
        "filter-category", "filter-priority", "filter-assignee", "reset-filters",
        "dashboard-success", "dashboard-alert", "loading-state", "dashboard-announcer", "dashboard-content",
        "empty-state", "last-updated", "scope-description", "user-initials", "user-name",
        "user-role", "logout-button", "menu-button", "mobile-nav", "kpi-open",
        "kpi-open-note", "kpi-reopened", "kpi-reopened-note", "kpi-response",
        "kpi-response-note", "kpi-sla", "kpi-sla-note", "kpi-satisfaction",
        "kpi-satisfaction-note", "kpi-total", "kpi-total-note", "status-total",
        "status-breakdown", "sla-ring", "sla-ring-value", "sla-response-rate",
        "sla-resolution-rate", "sla-excluded", "priority-breakdown", "category-breakdown",
    ];
    for (const id of ids) {
        elements[toCamelCase(id)] = document.getElementById(id);
    }
}

function toCamelCase(value) {
    return value.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
}

function readStoredUser() {
    const value = sessionStorage.getItem(STORAGE_KEYS.user);
    if (!value) return null;
    try {
        return JSON.parse(value);
    } catch (_error) {
        for (const key of Object.values(STORAGE_KEYS)) sessionStorage.removeItem(key);
        return null;
    }
}

function storeSession(tokenData) {
    state.accessToken = tokenData.access_token;
    state.refreshToken = tokenData.refresh_token;
    state.user = tokenData.user;
    sessionStorage.setItem(STORAGE_KEYS.accessToken, state.accessToken);
    sessionStorage.setItem(STORAGE_KEYS.refreshToken, state.refreshToken);
    sessionStorage.setItem(STORAGE_KEYS.user, JSON.stringify(state.user));
}

function clearSession() {
    state.accessToken = null;
    state.refreshToken = null;
    state.user = null;
    for (const key of Object.values(STORAGE_KEYS)) sessionStorage.removeItem(key);
}

function roleCodes(user = state.user) {
    return new Set((user?.roles || []).map((role) => role.role_code));
}

function dashboardRole() {
    const roles = roleCodes();
    if (roles.has("ADMIN")) return "ADMIN";
    if (roles.has("PROCESSOR")) return "PROCESSOR";
    return null;
}

async function handleLogin(event) {
    event.preventDefault();
    setLoginError("");
    setLoginBusy(true);
    try {
        const response = await fetch(`${API_PREFIX}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({
                email: elements.loginEmail.value.trim(),
                password: elements.loginPassword.value,
            }),
        });
        const payload = await parseResponse(response);
        if (!response.ok) throw new Error(errorMessage(payload, "Đăng nhập không thành công."));
        storeSession(payload.data);
        elements.loginPassword.value = "";
        if (!dashboardRole()) {
            clearSession();
            showAccessDenied("Dashboard chỉ dành cho quản trị viên và nhân viên xử lý.");
            return;
        }
        await startDashboard();
    } catch (error) {
        setLoginError(
            error instanceof TypeError
                ? "Không thể kết nối đến máy chủ. Vui lòng thử lại."
                : error.message,
        );
    } finally {
        setLoginBusy(false);
    }
}

async function startDashboard() {
    if (!dashboardRole()) {
        clearSession();
        showAccessDenied("Tài khoản không có quyền xem dashboard.");
        return;
    }
    elements.authPanel.hidden = true;
    elements.dashboardShell.hidden = false;
    renderUser();
    setAssigneeForRole();
    try {
        await loadFilterOptions();
        await loadDashboard();
    } catch (error) {
        if (state.accessToken) showDashboardError(error.message);
    }
}

function showLogin(message = "") {
    elements.dashboardShell.hidden = true;
    elements.authPanel.hidden = false;
    elements.accessDeniedState.hidden = true;
    elements.loginForm.hidden = false;
    setLoginError(message);
    window.setTimeout(() => elements.loginEmail.focus(), 0);
}

function showAccessDenied(message) {
    elements.dashboardShell.hidden = true;
    elements.authPanel.hidden = false;
    elements.loginForm.hidden = true;
    elements.accessDeniedMessage.textContent = message;
    elements.accessDeniedState.hidden = false;
    window.setTimeout(() => elements.deniedBackToLogin.focus(), 0);
}

function renderUser() {
    const user = state.user;
    const role = dashboardRole();
    elements.userName.textContent = user.full_name;
    elements.userRole.textContent = role === "ADMIN" ? "Quản trị viên" : "Nhân viên xử lý";
    elements.userInitials.textContent = initials(user.full_name);
    elements.scopeDescription.textContent = role === "ADMIN"
        ? "Theo dõi KPI toàn hệ thống và lọc theo người xử lý."
        : "Theo dõi KPI của các ticket hiện được phân công cho bạn.";
}

function initials(name) {
    const words = String(name || "").trim().split(/\s+/).filter(Boolean);
    return words.slice(-2).map((word) => word[0]).join("").toUpperCase() || "--";
}

function setAssigneeForRole() {
    clearOptions(elements.filterAssignee);
    if (dashboardRole() === "PROCESSOR") {
        appendOption(elements.filterAssignee, String(state.user.user_id), `${state.user.full_name} (Tôi)`);
        elements.filterAssignee.value = String(state.user.user_id);
        elements.filterAssignee.disabled = true;
    } else {
        appendOption(elements.filterAssignee, "", "Tất cả người xử lý");
        elements.filterAssignee.disabled = false;
    }
}

async function loadFilterOptions() {
    const requests = [apiRequest("/categories"), apiRequest("/priorities")];
    if (dashboardRole() === "ADMIN") {
        requests.push(apiRequest("/admin/users?role_code=PROCESSOR&is_active=true&page=1&page_size=100"));
    }
    const [categories, priorities, users] = await Promise.all(requests);
    populateSelect(elements.filterCategory, categories, "category_id", "category_name", "Tất cả danh mục");
    populateSelect(
        elements.filterPriority,
        priorities,
        "priority_id",
        (item) => `${item.priority_code} · ${item.priority_name}`,
        "Tất cả ưu tiên",
    );
    if (dashboardRole() === "ADMIN") {
        populateSelect(elements.filterAssignee, users.items, "user_id", "full_name", "Tất cả người xử lý");
    }
}

function populateSelect(select, items, valueKey, labelKey, placeholder) {
    clearOptions(select);
    appendOption(select, "", placeholder);
    for (const item of items || []) {
        const label = typeof labelKey === "function" ? labelKey(item) : item[labelKey];
        appendOption(select, String(item[valueKey]), label);
    }
}

function clearOptions(select) {
    select.replaceChildren();
}

function appendOption(select, value, label) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    select.append(option);
}

async function handleFilterSubmit(event) {
    event.preventDefault();
    if (!validateDateRange()) return;
    await loadDashboard();
}

function validateDateRange() {
    const from = elements.filterFrom.value;
    const to = elements.filterTo.value;
    if (from && to && from > to) {
        showDashboardError("Từ ngày phải nhỏ hơn hoặc bằng đến ngày.");
        elements.filterFrom.focus();
        return false;
    }
    return true;
}

function setDefaultDates() {
    const today = new Date();
    const from = new Date(today);
    from.setDate(from.getDate() - 29);
    elements.filterFrom.value = dateInputValue(from);
    elements.filterTo.value = dateInputValue(today);
}

function dateInputValue(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function resetFilters() {
    setDefaultDates();
    elements.filterCategory.value = "";
    elements.filterPriority.value = "";
    if (dashboardRole() === "ADMIN") elements.filterAssignee.value = "";
    loadDashboard();
}

function buildDashboardQuery() {
    const query = new URLSearchParams();
    const from = dateBoundary(elements.filterFrom.value, false);
    const to = dateBoundary(elements.filterTo.value, true);
    if (from) query.set("from", from);
    if (to) query.set("to", to);
    if (elements.filterCategory.value) query.set("category_id", elements.filterCategory.value);
    if (elements.filterPriority.value) query.set("priority_id", elements.filterPriority.value);
    if (dashboardRole() === "ADMIN" && elements.filterAssignee.value) {
        query.set("assignee_id", elements.filterAssignee.value);
    }
    return query.toString();
}

function dateBoundary(value, endOfDay) {
    if (!value) return null;
    const parts = value.split("-").map(Number);
    const date = endOfDay
        ? new Date(parts[0], parts[1] - 1, parts[2], 23, 59, 59, 999)
        : new Date(parts[0], parts[1] - 1, parts[2], 0, 0, 0, 0);
    return date.toISOString();
}

async function loadDashboard() {
    if (state.loading) return;
    setDashboardBusy(true);
    showDashboardError("");
    showDashboardSuccess("");
    try {
        const query = buildDashboardQuery();
        const [overview, sla] = await Promise.all([
            apiRequest(`/dashboard/overview?${query}`),
            apiRequest(`/dashboard/sla-performance?${query}`),
        ]);
        renderDashboard(overview, sla);
        const now = new Date();
        elements.lastUpdated.dateTime = now.toISOString();
        elements.lastUpdated.textContent = now.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
        elements.dashboardAnnouncer.textContent = `Dashboard đã cập nhật. Tổng số ${overview.ticket_counts.total} ticket.`;
        showDashboardSuccess("Dữ liệu dashboard đã được cập nhật thành công.");
    } catch (error) {
        if (state.accessToken) showDashboardError(error.message);
    } finally {
        setDashboardBusy(false);
    }
}

function renderDashboard(overview, sla) {
    const counts = overview.ticket_counts;
    setMetric(elements.kpiOpen, counts.open, elements.kpiOpenNote, `${counts.total} ticket trong kỳ`);
    setMetric(elements.kpiReopened, counts.reopened, elements.kpiReopenedNote, `${counts.closed} ticket đã đóng`);
    setMetric(
        elements.kpiResponse,
        formatMinutes(overview.average_first_response_minutes),
        elements.kpiResponseNote,
        sampleLabel(overview.first_response_sample_size, "phản hồi"),
        overview.average_first_response_minutes,
    );
    setMetric(
        elements.kpiSla,
        formatRate(overview.sla_compliance.compliance_rate),
        elements.kpiSlaNote,
        sampleLabel(overview.sla_compliance.total, "mốc SLA"),
        overview.sla_compliance.compliance_rate,
    );
    setMetric(
        elements.kpiSatisfaction,
        formatScore(overview.satisfaction.average_score),
        elements.kpiSatisfactionNote,
        sampleLabel(overview.satisfaction.rated_tickets, "đánh giá"),
        overview.satisfaction.average_score,
    );
    setMetric(elements.kpiTotal, counts.total, elements.kpiTotalNote, `${counts.closed} đóng · ${counts.rejected} từ chối`);

    elements.statusTotal.textContent = `${formatNumber(counts.total)} ticket`;
    renderStatusBreakdown(overview.by_status, counts.total);
    renderPriorityBreakdown(overview.by_priority);
    renderCategoryBreakdown(overview.by_category);
    renderSla(sla);

    const isEmpty = counts.total === 0;
    elements.emptyState.hidden = !isEmpty;
    document.querySelector(".dashboard-grid").hidden = isEmpty;
}

function setMetric(valueElement, value, noteElement, note, rawValue = value) {
    valueElement.textContent = value ?? "—";
    valueElement.dataset.rawValue = rawValue == null ? "" : String(rawValue);
    noteElement.textContent = note;
}

function sampleLabel(size, noun) {
    return size > 0 ? `${formatNumber(size)} ${noun}` : "Chưa có mẫu dữ liệu";
}

function formatNumber(value) {
    return Number(value || 0).toLocaleString("vi-VN");
}

function formatMinutes(value) {
    if (value == null) return "—";
    if (value < 60) return `${Number(value).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} phút`;
    return `${(value / 60).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} giờ`;
}

function formatRate(value) {
    return value == null ? "—" : `${Number(value).toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%`;
}

function formatScore(value) {
    return value == null ? "—" : `${Number(value).toLocaleString("vi-VN", { maximumFractionDigits: 1 })}/5`;
}

function renderStatusBreakdown(items, total) {
    elements.statusBreakdown.replaceChildren();
    if (!items?.length) return appendEmpty(elements.statusBreakdown, "Chưa có dữ liệu trạng thái.");
    const fragment = document.createDocumentFragment();
    for (const item of items) {
        const wrapper = document.createElement("div");
        const heading = document.createElement("div");
        const label = document.createElement("span");
        const count = document.createElement("strong");
        const track = document.createElement("div");
        const fill = document.createElement("div");
        const percentage = total > 0 ? (item.count / total) * 100 : 0;

        wrapper.className = "bar-item";
        heading.className = "bar-item-head";
        label.textContent = item.status_name;
        count.textContent = `${formatNumber(item.count)} · ${percentage.toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%`;
        track.className = "bar-track";
        track.setAttribute("role", "progressbar");
        track.setAttribute("aria-label", item.status_name);
        track.setAttribute("aria-valuemin", "0");
        track.setAttribute("aria-valuemax", String(total));
        track.setAttribute("aria-valuenow", String(item.count));
        fill.className = "bar-fill";
        fill.style.setProperty("--bar-width", `${percentage}%`);
        fill.style.setProperty("--bar-color", STATUS_COLORS[item.status_code] || "#71809a");
        heading.append(label, count);
        track.append(fill);
        wrapper.append(heading, track);
        fragment.append(wrapper);
    }
    elements.statusBreakdown.append(fragment);
}

function renderPriorityBreakdown(items) {
    elements.priorityBreakdown.replaceChildren();
    if (!items?.length) return appendEmpty(elements.priorityBreakdown, "Chưa có dữ liệu ưu tiên.");
    for (const item of items) {
        const row = document.createElement("div");
        const code = document.createElement("span");
        const name = document.createElement("span");
        const count = document.createElement("strong");
        row.className = "compact-item";
        code.className = "priority-code";
        code.textContent = item.priority_code;
        name.textContent = item.priority_name;
        count.textContent = formatNumber(item.count);
        row.append(code, name, count);
        elements.priorityBreakdown.append(row);
    }
}

function renderCategoryBreakdown(items) {
    elements.categoryBreakdown.replaceChildren();
    if (!items?.length) return appendEmpty(elements.categoryBreakdown, "Chưa có dữ liệu danh mục.");
    for (const item of items) {
        const row = document.createElement("div");
        const name = document.createElement("span");
        const count = document.createElement("strong");
        row.className = "category-item";
        name.textContent = item.category_name;
        name.title = item.category_name;
        count.textContent = formatNumber(item.count);
        row.append(name, count);
        elements.categoryBreakdown.append(row);
    }
}

function appendEmpty(container, message) {
    const empty = document.createElement("p");
    empty.className = "list-empty";
    empty.textContent = message;
    container.append(empty);
}

function renderSla(sla) {
    const rate = sla.overall.compliance_rate;
    elements.slaRing.style.setProperty("--rate", String(rate ?? 0));
    elements.slaRing.classList.toggle("is-empty", rate == null);
    elements.slaRingValue.textContent = formatRate(rate);
    elements.slaRing.setAttribute(
        "aria-label",
        rate == null ? "Chưa có dữ liệu SLA" : `Tỷ lệ đúng SLA tổng thể ${formatRate(rate)}`,
    );
    elements.slaResponseRate.textContent = formatRate(sla.response.compliance_rate);
    elements.slaResolutionRate.textContent = formatRate(sla.resolution.compliance_rate);
    elements.slaExcluded.textContent = formatNumber(sla.excluded_not_applicable);
}

async function apiRequest(path, options = {}, retry = true) {
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    if (state.accessToken) headers.set("Authorization", `Bearer ${state.accessToken}`);
    let response;
    try {
        response = await fetch(`${API_PREFIX}${path}`, { ...options, headers });
    } catch (_error) {
        throw new Error("Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối và thử lại.");
    }
    if (response.status === 401 && retry && state.refreshToken) {
        const refreshed = await refreshSession();
        if (refreshed) return apiRequest(path, options, false);
    }
    const payload = await parseResponse(response);
    if (!response.ok) {
        if (response.status === 401) {
            clearSession();
            showLogin("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
        }
        if (response.status === 403 && path.startsWith("/dashboard/")) {
            clearSession();
            showAccessDenied(errorMessage(payload, "Tài khoản không có quyền xem dashboard."));
        }
        throw new Error(errorMessage(payload, `Yêu cầu thất bại (${response.status}).`));
    }
    return payload?.data;
}

async function refreshSession() {
    if (state.refreshPromise) return state.refreshPromise;
    state.refreshPromise = performRefreshSession();
    try {
        return await state.refreshPromise;
    } finally {
        state.refreshPromise = null;
    }
}

async function performRefreshSession() {
    try {
        const response = await fetch(`${API_PREFIX}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({ refresh_token: state.refreshToken }),
        });
        const payload = await parseResponse(response);
        if (!response.ok) return false;
        storeSession(payload.data);
        if (!dashboardRole()) {
            clearSession();
            return false;
        }
        renderUser();
        return true;
    } catch (_error) {
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
        const field = payload.errors[0].field ? `${payload.errors[0].field}: ` : "";
        return `${payload.message} ${field}${payload.errors[0].message}`;
    }
    if (payload?.message) return payload.message;
    if (payload?.detail) return typeof payload.detail === "string" ? payload.detail : fallback;
    return fallback;
}

async function handleLogout() {
    const refreshToken = state.refreshToken;
    try {
        if (refreshToken) {
            await apiRequest("/auth/logout", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ refresh_token: refreshToken }),
            }, false);
        }
    } catch (_error) {
        // Local session is still cleared when the server is unavailable.
    } finally {
        clearSession();
        showLogin();
    }
}

function toggleMobileNavigation() {
    const willOpen = elements.mobileNav.hidden;
    elements.mobileNav.hidden = !willOpen;
    elements.menuButton.setAttribute("aria-expanded", String(willOpen));
    elements.menuButton.setAttribute("aria-label", willOpen ? "Đóng điều hướng" : "Mở điều hướng");
}

function setLoginBusy(busy) {
    elements.loginButton.disabled = busy;
    elements.loginButton.textContent = busy ? "Đang đăng nhập…" : "Đăng nhập";
}

function setDashboardBusy(busy) {
    state.loading = busy;
    elements.loadingState.hidden = !busy;
    elements.dashboardContent.setAttribute("aria-busy", String(busy));
    for (const button of elements.dashboardFilters.querySelectorAll("button")) button.disabled = busy;
}

function setLoginError(message) {
    elements.loginError.textContent = message;
    elements.loginError.hidden = !message;
}

function showDashboardError(message) {
    elements.dashboardAlert.textContent = message;
    elements.dashboardAlert.hidden = !message;
    if (message) showDashboardSuccess("");
}

function showDashboardSuccess(message) {
    elements.dashboardSuccess.textContent = message;
    elements.dashboardSuccess.hidden = !message;
}
