"use strict";

(() => {
    const API_PREFIX = "/api/v1";

    const STORAGE_KEYS = Object.freeze({
        accessToken: "helpdesk.dashboard.accessToken",
        refreshToken: "helpdesk.dashboard.refreshToken",
        user: "helpdesk.dashboard.user",
    });

    const listState = {
        page: 1,
        pageSize: 20,
        totalPages: 0,
        loading: false,
    };

    const elements = {};

    document.addEventListener("DOMContentLoaded", initialize);
    window.addEventListener("portal:authenticated", startTicketWorkspace);

    function initialize() {
        cacheElements();

        elements.filterForm.addEventListener("submit", handleFilterSubmit);
        elements.filterReset.addEventListener("click", resetFilters);
        elements.pagePrevious.addEventListener("click", showPreviousPage);
        elements.pageNext.addEventListener("click", showNextPage);
    }

    function cacheElements() {
        elements.filterForm = document.getElementById("ticket-filter-form");
        elements.filterQuery = document.getElementById("ticket-filter-query");
        elements.filterStatus = document.getElementById("ticket-filter-status");
        elements.filterCategory = document.getElementById("ticket-filter-category");
        elements.filterPriority = document.getElementById("ticket-filter-priority");
        elements.filterSubmit = document.getElementById("ticket-filter-submit");
        elements.filterReset = document.getElementById("ticket-filter-reset");
        elements.listSummary = document.getElementById("ticket-list-summary");
        elements.listLoading = document.getElementById("ticket-list-loading");
        elements.listError = document.getElementById("ticket-list-error");
        elements.listEmpty = document.getElementById("ticket-list-empty");
        elements.tableWrapper = document.getElementById("ticket-table-wrapper");
        elements.tableBody = document.getElementById("ticket-table-body");
        elements.pagination = document.getElementById("ticket-pagination");
        elements.pagePrevious = document.getElementById("ticket-page-previous");
        elements.pageNext = document.getElementById("ticket-page-next");
        elements.pageInformation = document.getElementById("ticket-page-information");
    }

    async function startTicketWorkspace() {
        listState.page = 1;
        clearListError();

        try {
            await loadCatalogOptions();
            await loadTickets();
        } catch (error) {
            showListError(error.message);
        }
    }

    async function loadCatalogOptions() {
        const [statuses, categories, priorities] = await Promise.all([
            apiRequest("/ticket-statuses"),
            apiRequest("/categories"),
            apiRequest("/priorities"),
        ]);

        populateSelect(
            elements.filterStatus,
            statuses,
            "status_code",
            "status_name",
            "Tất cả trạng thái",
        );

        populateSelect(
            elements.filterCategory,
            categories,
            "category_id",
            "category_name",
            "Tất cả danh mục",
        );

        populateSelect(
            elements.filterPriority,
            priorities,
            "priority_id",
            (item) => `${item.priority_code} · ${item.priority_name}`,
            "Tất cả ưu tiên",
        );
    }

    function populateSelect(select, items, valueKey, labelKey, placeholder) {
        select.replaceChildren();

        const defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = placeholder;
        select.append(defaultOption);

        for (const item of items || []) {
            const option = document.createElement("option");
            const label = typeof labelKey === "function"
                ? labelKey(item)
                : item[labelKey];

            option.value = String(item[valueKey]);
            option.textContent = label;
            select.append(option);
        }
    }

    async function handleFilterSubmit(event) {
        event.preventDefault();
        listState.page = 1;
        await loadTickets();
    }

    async function resetFilters() {
        elements.filterQuery.value = "";
        elements.filterStatus.value = "";
        elements.filterCategory.value = "";
        elements.filterPriority.value = "";
        listState.page = 1;
        await loadTickets();
    }

    async function showPreviousPage() {
        if (listState.page <= 1) return;
        listState.page -= 1;
        await loadTickets();
    }

    async function showNextPage() {
        if (listState.page >= listState.totalPages) return;
        listState.page += 1;
        await loadTickets();
    }

    function buildTicketQuery() {
        const query = new URLSearchParams({
            page: String(listState.page),
            page_size: String(listState.pageSize),
            sort: "-created_at",
        });

        const search = elements.filterQuery.value.trim();

        if (search) query.set("q", search);
        if (elements.filterStatus.value) {
            query.set("status", elements.filterStatus.value);
        }
        if (elements.filterCategory.value) {
            query.set("category_id", elements.filterCategory.value);
        }
        if (elements.filterPriority.value) {
            query.set("priority_id", elements.filterPriority.value);
        }

        return query.toString();
    }

    async function loadTickets() {
        if (listState.loading) return;

        setListBusy(true);
        clearListError();

        try {
            const data = await apiRequest(`/tickets?${buildTicketQuery()}`);
            renderTicketList(data);
        } catch (error) {
            showListError(error.message);
        } finally {
            setListBusy(false);
        }
    }

    function renderTicketList(data) {
        listState.page = data.page;
        listState.totalPages = data.total_pages;

        elements.tableBody.replaceChildren();
        elements.listSummary.textContent =
            `${formatNumber(data.total)} ticket trong phạm vi truy cập`;

        const hasTickets = data.items.length > 0;

        elements.listEmpty.hidden = hasTickets;
        elements.tableWrapper.hidden = !hasTickets;
        elements.pagination.hidden = !hasTickets;

        for (const ticket of data.items) {
            elements.tableBody.append(createTicketRow(ticket));
        }

        const displayedTotalPages = Math.max(data.total_pages, 1);

        elements.pageInformation.textContent =
            `Trang ${data.page}/${displayedTotalPages}`;

        elements.pagePrevious.disabled = data.page <= 1;
        elements.pageNext.disabled =
            data.total_pages === 0 || data.page >= data.total_pages;
    }

    function createTicketRow(ticket) {
        const row = document.createElement("tr");

        row.append(
            createCell(ticket.ticket_code, "Mã ticket", "ticket-code"),
            createTicketContentCell(ticket),
            createPriorityCell(ticket),
            createStatusCell(ticket),
            createCell(
                ticket.current_assignee?.full_name || "Chưa phân công",
                "Người xử lý",
            ),
            createCell(formatDateTime(ticket.created_at), "Ngày tạo"),
        );

        return row;
    }

    function createTicketContentCell(ticket) {
        const cell = document.createElement("td");
        const title = document.createElement("strong");
        const category = document.createElement("span");

        cell.dataset.label = "Nội dung";
        cell.className = "ticket-content";
        title.textContent = ticket.title;
        category.textContent = ticket.category.category_name;

        cell.append(title, category);
        return cell;
    }

    function createPriorityCell(ticket) {
        const cell = document.createElement("td");
        const badge = document.createElement("span");

        cell.dataset.label = "Ưu tiên";
        badge.className =
            `priority-badge priority-badge--${ticket.priority.priority_code.toLowerCase()}`;
        badge.textContent =
            `${ticket.priority.priority_code} · ${ticket.priority.priority_name}`;

        cell.append(badge);
        return cell;
    }

    function createStatusCell(ticket) {
        const cell = document.createElement("td");
        const badge = document.createElement("span");
        const statusClass = ticket.status.status_code
            .toLowerCase()
            .replaceAll("_", "-");

        cell.dataset.label = "Trạng thái";
        badge.className = `status-badge status-badge--${statusClass}`;
        badge.textContent = ticket.status.status_name;

        cell.append(badge);
        return cell;
    }

    function createCell(value, label, className = "") {
        const cell = document.createElement("td");

        cell.dataset.label = label;
        cell.textContent = value;

        if (className) cell.className = className;

        return cell;
    }

    function formatDateTime(value) {
        const date = new Date(value);

        if (Number.isNaN(date.getTime())) return "—";

        return date.toLocaleString("vi-VN", {
            dateStyle: "short",
            timeStyle: "short",
        });
    }

    function formatNumber(value) {
        return Number(value || 0).toLocaleString("vi-VN");
    }

    function setListBusy(busy) {
        listState.loading = busy;
        elements.listLoading.hidden = !busy;
        elements.filterSubmit.disabled = busy;
        elements.filterReset.disabled = busy;
        elements.pagePrevious.disabled = busy;
        elements.pageNext.disabled = busy;
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

    async function apiRequest(path, options = {}, retry = true) {
        const headers = new Headers(options.headers || {});
        const accessToken = sessionStorage.getItem(STORAGE_KEYS.accessToken);

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
            const refreshed = await refreshSession();

            if (refreshed) {
                return apiRequest(path, options, false);
            }
        }

        const payload = await parseResponse(response);

        if (!response.ok) {
            if (response.status === 401) {
                clearStoredSession();
                window.location.reload();
            }

            throw new Error(
                errorMessage(payload, `Yêu cầu thất bại (${response.status}).`),
            );
        }

        return payload?.data;
    }

    async function refreshSession() {
        const refreshToken =
            sessionStorage.getItem(STORAGE_KEYS.refreshToken);

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

            if (!response.ok || !payload?.data) return false;

            sessionStorage.setItem(
                STORAGE_KEYS.accessToken,
                payload.data.access_token,
            );
            sessionStorage.setItem(
                STORAGE_KEYS.refreshToken,
                payload.data.refresh_token,
            );
            sessionStorage.setItem(
                STORAGE_KEYS.user,
                JSON.stringify(payload.data.user),
            );

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
})();