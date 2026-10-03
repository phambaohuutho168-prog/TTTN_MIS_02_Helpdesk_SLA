(() => {
    "use strict";

    const API_PREFIX = "/api/v1";

    const STORAGE_KEYS = Object.freeze({
        accessToken: "helpdesk.dashboard.accessToken",
        refreshToken: "helpdesk.dashboard.refreshToken",
        user: "helpdesk.dashboard.user",
    });

    const monitorState = {
        user: null,
        page: 1,
        pageSize: 20,
        totalPages: 0,
        loading: false,
    };

    const elements = {};

    document.addEventListener("DOMContentLoaded", initialize);
    window.addEventListener(
        "portal:authenticated",
        startSlaMonitor,
    );

    function initialize() {
        cacheElements();

        elements.reload.addEventListener(
            "click",
            loadSlaEvents,
        );
        elements.filterForm.addEventListener(
            "submit",
            handleFilterSubmit,
        );
        elements.filterReset.addEventListener(
            "click",
            resetFilters,
        );
        elements.pagePrevious.addEventListener(
            "click",
            showPreviousPage,
        );
        elements.pageNext.addEventListener(
            "click",
            showNextPage,
        );
    }

    function cacheElements() {
        elements.section =
            document.getElementById("sla-monitor-section");
        elements.total =
            document.getElementById("sla-monitor-total");
        elements.reload =
            document.getElementById("sla-monitor-reload");
        elements.filterForm =
            document.getElementById("sla-monitor-filter-form");
        elements.filterState =
            document.getElementById("sla-monitor-filter-state");
        elements.filterType =
            document.getElementById("sla-monitor-filter-type");
        elements.filterTicket =
            document.getElementById("sla-monitor-filter-ticket");
        elements.filterFrom =
            document.getElementById("sla-monitor-filter-from");
        elements.filterTo =
            document.getElementById("sla-monitor-filter-to");
        elements.pageSize =
            document.getElementById("sla-monitor-page-size");
        elements.filterReset =
            document.getElementById("sla-monitor-filter-reset");
        elements.summary =
            document.getElementById("sla-monitor-summary");
        elements.loading =
            document.getElementById("sla-monitor-loading");
        elements.error =
            document.getElementById("sla-monitor-error");
        elements.empty =
            document.getElementById("sla-monitor-empty");
        elements.tableWrapper =
            document.getElementById("sla-monitor-table-wrapper");
        elements.tableBody =
            document.getElementById("sla-monitor-table-body");
        elements.pagination =
            document.getElementById("sla-monitor-pagination");
        elements.pagePrevious =
            document.getElementById("sla-monitor-page-previous");
        elements.pageInformation =
            document.getElementById("sla-monitor-page-information");
        elements.pageNext =
            document.getElementById("sla-monitor-page-next");
    }

    async function startSlaMonitor() {
        monitorState.user = readStoredUser();

        const role = primaryRole(monitorState.user);

        if (!["ADMIN", "PROCESSOR"].includes(role)) {
            elements.section.hidden = true;
            return;
        }

        elements.section.hidden = false;
        monitorState.page = 1;
        monitorState.pageSize = Number(elements.pageSize.value);

        await loadSlaEvents();
    }

    function readStoredUser() {
        const value = sessionStorage.getItem(STORAGE_KEYS.user);

        if (!value) return null;

        try {
            return JSON.parse(value);
        } catch (_error) {
            return null;
        }
    }

    function primaryRole(user) {
        const roles = new Set(
            (user?.roles || []).map((role) => role.role_code),
        );

        if (roles.has("ADMIN")) return "ADMIN";
        if (roles.has("PROCESSOR")) return "PROCESSOR";
        if (roles.has("REQUESTER")) return "REQUESTER";

        return null;
    }

    async function handleFilterSubmit(event) {
        event.preventDefault();

        if (!validateDateRange()) return;

        monitorState.page = 1;
        monitorState.pageSize =
            Number(elements.pageSize.value) || 20;

        await loadSlaEvents();
    }

    async function resetFilters() {
        elements.filterForm.reset();
        monitorState.page = 1;
        monitorState.pageSize = 20;

        hideError();
        await loadSlaEvents();
    }

    async function showPreviousPage() {
        if (monitorState.page <= 1 || monitorState.loading) {
            return;
        }

        monitorState.page -= 1;
        await loadSlaEvents();
    }

    async function showNextPage() {
        if (
            monitorState.page >= monitorState.totalPages ||
            monitorState.loading
        ) {
            return;
        }

        monitorState.page += 1;
        await loadSlaEvents();
    }

    function validateDateRange() {
        const fromValue = elements.filterFrom.value;
        const toValue = elements.filterTo.value;

        hideError();

        if (
            fromValue &&
            toValue &&
            new Date(fromValue) > new Date(toValue)
        ) {
            showError(
                "Thời điểm bắt đầu phải trước thời điểm kết thúc.",
            );
            return false;
        }

        return true;
    }

    async function loadSlaEvents() {
        if (monitorState.loading) return;

        monitorState.loading = true;
        setLoadingState(true);
        hideError();

        try {
            const query = buildQuery();
            const pageData = await apiRequest(
                `/sla/breaches?${query.toString()}`,
            );

            renderSlaEvents(pageData);
        } catch (error) {
            elements.tableBody.replaceChildren();
            elements.tableWrapper.hidden = true;
            elements.empty.hidden = true;
            elements.pagination.hidden = true;
            elements.summary.textContent =
                "Không thể tải dữ liệu giám sát SLA.";

            showError(error.message);
        } finally {
            monitorState.loading = false;
            setLoadingState(false);
        }
    }

    function buildQuery() {
        const query = new URLSearchParams();

        if (elements.filterState.value) {
            query.append("state", elements.filterState.value);
        }

        if (elements.filterType.value) {
            query.set("sla_type", elements.filterType.value);
        }

        if (elements.filterTicket.value) {
            query.set(
                "ticket_id",
                elements.filterTicket.value,
            );
        }

        const triggeredFrom =
            toIsoDateTime(elements.filterFrom.value);
        const triggeredTo =
            toIsoDateTime(elements.filterTo.value);

        if (triggeredFrom) {
            query.set("triggered_from", triggeredFrom);
        }

        if (triggeredTo) {
            query.set("triggered_to", triggeredTo);
        }

        query.set("page", String(monitorState.page));
        query.set(
            "page_size",
            String(monitorState.pageSize),
        );

        return query;
    }

    function toIsoDateTime(value) {
        if (!value) return "";

        const date = new Date(value);

        return Number.isNaN(date.getTime())
            ? ""
            : date.toISOString();
    }

    function renderSlaEvents(pageData) {
        const items = Array.isArray(pageData?.items)
            ? pageData.items
            : [];
        const total = Number(pageData?.total || 0);
        const currentPage = Number(pageData?.page || 1);
        const totalPages = Number(pageData?.total_pages || 0);

        monitorState.page = currentPage;
        monitorState.totalPages = totalPages;

        elements.total.textContent =
            `${total} sự kiện`;
        elements.summary.textContent =
            total === 0
                ? "Không có cảnh báo SLA phù hợp."
                : `Đang hiển thị ${items.length} trong ` +
                  `${total} sự kiện SLA.`;

        elements.tableBody.replaceChildren();

        if (items.length === 0) {
            elements.empty.hidden = false;
            elements.tableWrapper.hidden = true;
            elements.pagination.hidden = true;
            return;
        }

        elements.empty.hidden = true;

        for (const event of items) {
            elements.tableBody.append(
                createSlaEventRow(event),
            );
        }

        elements.tableWrapper.hidden = false;
        renderPagination();
    }

    function createSlaEventRow(event) {
        const row = document.createElement("tr");
        const state = normalizeEventState(event.state);

        row.className = `sla-monitor-row--${state}`;

        row.append(
            createTicketCell(event),
            createTypeCell(event),
            createStateCell(event),
            createDueDateCell(event),
            createDateCell(event.triggered_at),
            createAssigneeCell(event),
            createActionCell(event),
        );

        return row;
    }

    function createTicketCell(event) {
        const cell = document.createElement("td");
        const wrapper = document.createElement("div");
        const code = document.createElement("strong");
        const title = document.createElement("span");
        const meta = document.createElement("small");
        const ticket = event.ticket || {};
        const priority = ticket.priority || {};

        wrapper.className = "sla-monitor-ticket";
        code.textContent = ticket.ticket_code || "—";
        title.textContent = ticket.title || "Không có tiêu đề";
        meta.textContent = [
            priority.priority_code,
            priority.priority_name,
            formatTicketStatus(ticket.current_status_code),
        ]
            .filter(Boolean)
            .join(" · ");

        wrapper.append(code, title, meta);
        cell.append(wrapper);

        return cell;
    }

    function createTypeCell(event) {
        const cell = document.createElement("td");
        const wrapper = document.createElement("div");
        const type = document.createElement("strong");
        const cycle = document.createElement("small");

        wrapper.className = "sla-monitor-meta";
        type.textContent = formatSlaType(event.sla_type);
        cycle.textContent = `Chu kỳ ${event.cycle_no}`;

        wrapper.append(type, cycle);
        cell.append(wrapper);

        return cell;
    }

    function createStateCell(event) {
        const cell = document.createElement("td");
        const wrapper = document.createElement("div");
        const badge = document.createElement("span");
        const threshold = document.createElement("small");
        const state = normalizeEventState(event.state);

        wrapper.className = "sla-monitor-meta";
        badge.className =
            `sla-event-badge sla-event-badge--${state}`;
        badge.textContent = formatEventState(event.state);
        threshold.textContent =
            `Ngưỡng ${event.threshold_percent}%`;

        wrapper.append(badge, threshold);
        cell.append(wrapper);

        return cell;
    }

    function createDueDateCell(event) {
        const cell = document.createElement("td");
        const wrapper = document.createElement("div");
        const effective = document.createElement("strong");
        const original = document.createElement("small");

        wrapper.className = "sla-monitor-meta";
        effective.textContent =
            formatDateTime(event.effective_due_at);
        original.textContent =
            `Hạn gốc: ${formatDateTime(event.due_at)}`;

        wrapper.append(effective, original);
        cell.append(wrapper);

        return cell;
    }

    function createDateCell(value) {
        const cell = document.createElement("td");

        cell.textContent = formatDateTime(value);

        return cell;
    }

    function createAssigneeCell(event) {
        const cell = document.createElement("td");
        const wrapper = document.createElement("div");
        const name = document.createElement("strong");
        const email = document.createElement("small");
        const assignee = event.current_assignee;

        wrapper.className = "sla-monitor-meta";

        if (assignee) {
            name.textContent = assignee.full_name;
            email.textContent = assignee.email;
        } else {
            name.textContent = "Chưa phân công";
            email.textContent = "—";
        }

        wrapper.append(name, email);
        cell.append(wrapper);

        return cell;
    }

    function createActionCell(event) {
        const cell = document.createElement("td");
        const button = document.createElement("button");

        button.className =
            "button button--secondary sla-monitor-open-ticket";
        button.type = "button";
        button.textContent = "Mở ticket";

        button.addEventListener("click", () => {
            const ticketId = Number(event.ticket?.ticket_id);

            if (!ticketId) return;

            window.dispatchEvent(
                new CustomEvent("portal:open-ticket", {
                    detail: { ticketId },
                }),
            );
        });

        cell.append(button);

        return cell;
    }

    function renderPagination() {
        const visible = monitorState.totalPages > 1;

        elements.pagination.hidden = !visible;
        elements.pagePrevious.disabled =
            monitorState.page <= 1;
        elements.pageNext.disabled =
            monitorState.page >= monitorState.totalPages;

        elements.pageInformation.textContent =
            `Trang ${monitorState.page}/` +
            `${Math.max(monitorState.totalPages, 1)}`;
    }

    function normalizeEventState(value) {
        const state = String(value || "").toLowerCase();

        return ["warning", "overdue", "escalated"]
            .includes(state)
            ? state
            : "warning";
    }

    function formatEventState(value) {
        const labels = {
            WARNING: "Sắp đến hạn",
            OVERDUE: "Quá hạn",
            ESCALATED: "Đã escalation",
        };

        return labels[value] || value || "Chưa xác định";
    }

    function formatSlaType(value) {
        const labels = {
            RESPONSE: "Phản hồi",
            RESOLUTION: "Xử lý",
        };

        return labels[value] || value || "—";
    }

    function formatTicketStatus(value) {
        const labels = {
            OPEN: "Mới tạo",
            ASSIGNED: "Đã phân công",
            IN_PROGRESS: "Đang xử lý",
            PENDING_INFO: "Chờ bổ sung thông tin",
            RESOLVED: "Đã giải quyết",
            CLOSED: "Đã đóng",
            REOPENED: "Đã mở lại",
            REJECTED: "Đã từ chối",
        };

        return labels[value] || value || "";
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

    function setLoadingState(loading) {
        elements.loading.hidden = !loading;
        elements.reload.disabled = loading;
        elements.pagePrevious.disabled =
            loading || monitorState.page <= 1;
        elements.pageNext.disabled =
            loading ||
            monitorState.page >= monitorState.totalPages;
    }

    function showError(message) {
        elements.error.textContent =
            message || "Không thể tải dữ liệu SLA.";
        elements.error.hidden = false;
    }

    function hideError() {
        elements.error.textContent = "";
        elements.error.hidden = true;
    }

    async function apiRequest(path, options = {}) {
        let response = await authorizedFetch(path, options);

        if (response.status === 401) {
            const refreshed = await refreshSession();

            if (refreshed) {
                response = await authorizedFetch(path, options);
            }
        }

        const payload = await parseResponse(response);

        if (!response.ok) {
            if (response.status === 401) {
                clearStoredSession();
                window.location.reload();
            }

            throw new Error(
                errorMessage(
                    payload,
                    `Yêu cầu thất bại (${response.status}).`,
                ),
            );
        }

        return payload?.data;
    }

    function authorizedFetch(path, options) {
        const headers = new Headers(options.headers || {});
        const accessToken =
            sessionStorage.getItem(STORAGE_KEYS.accessToken);

        headers.set("Accept", "application/json");

        if (accessToken) {
            headers.set(
                "Authorization",
                `Bearer ${accessToken}`,
            );
        }

        return fetch(`${API_PREFIX}${path}`, {
            ...options,
            headers,
        });
    }

    async function refreshSession() {
        const refreshToken =
            sessionStorage.getItem(STORAGE_KEYS.refreshToken);

        if (!refreshToken) return false;

        try {
            const response = await fetch(
                `${API_PREFIX}/auth/refresh`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    body: JSON.stringify({
                        refresh_token: refreshToken,
                    }),
                },
            );
            const payload = await parseResponse(response);
            const tokenData = payload?.data;

            if (!response.ok || !tokenData?.access_token) {
                return false;
            }

            sessionStorage.setItem(
                STORAGE_KEYS.accessToken,
                tokenData.access_token,
            );

            if (tokenData.refresh_token) {
                sessionStorage.setItem(
                    STORAGE_KEYS.refreshToken,
                    tokenData.refresh_token,
                );
            }

            if (tokenData.user) {
                sessionStorage.setItem(
                    STORAGE_KEYS.user,
                    JSON.stringify(tokenData.user),
                );
                monitorState.user = tokenData.user;
            }

            return true;
        } catch (_error) {
            return false;
        }
    }

    function clearStoredSession() {
        for (const key of Object.values(STORAGE_KEYS)) {
            sessionStorage.removeItem(key);
        }
    }

    async function parseResponse(response) {
        if (response.status === 204) return null;

        const contentType =
            response.headers.get("content-type") || "";

        if (!contentType.includes("application/json")) {
            return null;
        }

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

            return (
                `${payload.message} ` +
                `${field}${payload.errors[0].message}`
            );
        }

        if (payload?.message) return payload.message;
        if (typeof payload?.detail === "string") {
            return payload.detail;
        }

        return fallback;
    }
})();