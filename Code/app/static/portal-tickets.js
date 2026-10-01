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
        elements.createToggle.addEventListener("click", toggleCreateForm);
        elements.createCancel.addEventListener("click", cancelCreateTicket);
        elements.createForm.addEventListener("submit", handleCreateTicket);
        elements.detailClose.addEventListener("click", closeTicketDetail);
        elements.detailDialog.addEventListener("click", handleDetailBackdropClick);
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
        elements.createSection = document.getElementById("ticket-create-section");
        elements.createToggle = document.getElementById("ticket-create-toggle");
        elements.createForm = document.getElementById("ticket-create-form");
        elements.createTitle = document.getElementById("ticket-create-title-input");
        elements.createCategory = document.getElementById("ticket-create-category");
        elements.createPriority = document.getElementById("ticket-create-priority");
        elements.createDescription = document.getElementById("ticket-create-description");
        elements.createSubmit = document.getElementById("ticket-create-submit");
        elements.createCancel = document.getElementById("ticket-create-cancel");
        elements.createError = document.getElementById("ticket-create-error");
        elements.portalMessage = document.getElementById("portal-message");
        elements.detailDialog = document.getElementById("ticket-detail-dialog");
        elements.detailClose = document.getElementById("ticket-detail-close");
        elements.detailLoading = document.getElementById("ticket-detail-loading");
        elements.detailError = document.getElementById("ticket-detail-error");
        elements.detailContent = document.getElementById("ticket-detail-content");
        elements.detailCode = document.getElementById("ticket-detail-code");
        elements.detailTitle = document.getElementById("ticket-detail-title");
        elements.detailPriority = document.getElementById("ticket-detail-priority");
        elements.detailStatus = document.getElementById("ticket-detail-status");
        elements.detailCategory = document.getElementById("ticket-detail-category");
        elements.detailRequester = document.getElementById("ticket-detail-requester");
        elements.detailAssignee = document.getElementById("ticket-detail-assignee");
        elements.detailCreatedAt = document.getElementById("ticket-detail-created-at");
        elements.detailUpdatedAt = document.getElementById("ticket-detail-updated-at");
        elements.detailDescription = document.getElementById("ticket-detail-description");
        elements.detailResponseDeadline = document.getElementById("ticket-detail-response-deadline",);
        elements.detailResolutionDeadline = document.getElementById("ticket-detail-resolution-deadline",);
        elements.detailActions = document.getElementById("ticket-detail-actions");
    }

    async function startTicketWorkspace() {
        configureCreateTicketSection();
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
        populateSelect(
            elements.createCategory,
            categories,
            "category_id",
            "category_name",
            "Chọn danh mục",
        );

        populateSelect(
            elements.createPriority,
            priorities,
            "priority_id",
            (item) => `${item.priority_code} · ${item.priority_name}`,
            "Chọn mức ưu tiên",
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
            createTicketCodeCell(ticket),
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

    function createTicketCodeCell(ticket) {
        const cell = document.createElement("td");
        const button = document.createElement("button");

        cell.dataset.label = "Mã ticket";
        button.type = "button";
        button.className = "ticket-link";
        button.textContent = ticket.ticket_code;
        button.addEventListener(
            "click",
            () => openTicketDetail(ticket.ticket_id),
        );

        cell.append(button);
        return cell;
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
    async function openTicketDetail(ticketId) {
        resetTicketDetail();

        if (!elements.detailDialog.open) {
            elements.detailDialog.showModal();
        }

        try {
            const ticket = await apiRequest(`/tickets/${ticketId}`);

            if (!ticket) {
                throw new Error("Không nhận được dữ liệu chi tiết ticket.");
            }

            renderTicketDetail(ticket);
        } catch (error) {
            elements.detailLoading.hidden = true;
            elements.detailContent.hidden = true;
            elements.detailError.textContent = error.message;
            elements.detailError.hidden = false;
        }
    }

    function resetTicketDetail() {
        elements.detailLoading.hidden = false;
        elements.detailError.hidden = true;
        elements.detailError.textContent = "";
        elements.detailContent.hidden = true;
        elements.detailActions.replaceChildren();
    }

    function renderTicketDetail(ticket) {
        elements.detailCode.textContent = ticket.ticket_code;
        elements.detailTitle.textContent = ticket.title;
        elements.detailCategory.textContent = ticket.category.category_name;
        elements.detailRequester.textContent =
            `${ticket.requester.full_name} (${ticket.requester.email})`;
        elements.detailAssignee.textContent =
            ticket.current_assignee?.full_name || "Chưa phân công";
        elements.detailCreatedAt.textContent =
            formatDateTime(ticket.created_at);
        elements.detailUpdatedAt.textContent =
            formatDateTime(ticket.updated_at);
        elements.detailDescription.textContent = ticket.description;

        const priorityCode = ticket.priority.priority_code.toLowerCase();

        elements.detailPriority.className =
            `priority-badge priority-badge--${priorityCode}`;
        elements.detailPriority.textContent =
            `${ticket.priority.priority_code} · ${ticket.priority.priority_name}`;

        const statusClass = ticket.status.status_code
            .toLowerCase()
            .replaceAll("_", "-");

        elements.detailStatus.className =
            `status-badge status-badge--${statusClass}`;
        elements.detailStatus.textContent = ticket.status.status_name;

        const responseSla = ticket.sla_summary?.response_sla;
        const resolutionCycles =
            ticket.sla_summary?.resolution_cycles || [];
        const resolutionSla =
            resolutionCycles.length > 0
                ? resolutionCycles[resolutionCycles.length - 1]
                : null;

        elements.detailResponseDeadline.textContent =
            formatSlaItem(responseSla);
        elements.detailResolutionDeadline.textContent =
            formatSlaItem(resolutionSla);

        elements.detailLoading.hidden = true;
        elements.detailError.hidden = true;
        elements.detailContent.hidden = false;
    }

    function formatSlaItem(slaItem) {
        if (!slaItem) return "Chưa thiết lập";

        const deadline = slaItem.effective_due_at || slaItem.due_at;
        const deadlineText = deadline
            ? formatDateTime(deadline)
            : "Chưa thiết lập";
        const statusLabel = slaItem.status?.label;

        return statusLabel
            ? `${deadlineText} · ${statusLabel}`
            : deadlineText;
    }

    function closeTicketDetail() {
        if (elements.detailDialog.open) {
            elements.detailDialog.close();
        }
    }

    function handleDetailBackdropClick(event) {
        if (event.target === elements.detailDialog) {
            closeTicketDetail();
        }
    }
    function currentPrimaryRole() {
        const storedUser = sessionStorage.getItem(STORAGE_KEYS.user);

        if (!storedUser) return null;

        try {
            const user = JSON.parse(storedUser);
            const roles = new Set(
                (user.roles || []).map((role) => role.role_code),
            );

            if (roles.has("ADMIN")) return "ADMIN";
            if (roles.has("PROCESSOR")) return "PROCESSOR";
            if (roles.has("REQUESTER")) return "REQUESTER";
        } catch (_error) {
            return null;
        }

        return null;
    }

    function configureCreateTicketSection() {
        const isRequester = currentPrimaryRole() === "REQUESTER";

        elements.createSection.hidden = !isRequester;
        closeCreateForm();
    }

    function toggleCreateForm() {
        const shouldOpen = elements.createForm.hidden;

        elements.createForm.hidden = !shouldOpen;
        elements.createToggle.setAttribute(
            "aria-expanded",
            String(shouldOpen),
        );
        elements.createToggle.textContent = shouldOpen
            ? "Đóng biểu mẫu"
            : "Tạo ticket mới";

        if (shouldOpen) {
            window.setTimeout(() => elements.createTitle.focus(), 0);
        }
    }

    function closeCreateForm() {
        elements.createForm.hidden = true;
        elements.createToggle.setAttribute("aria-expanded", "false");
        elements.createToggle.textContent = "Tạo ticket mới";
        clearCreateError();
    }

    function cancelCreateTicket() {
        elements.createForm.reset();
        closeCreateForm();
    }

    async function handleCreateTicket(event) {
        event.preventDefault();
        clearCreateError();

        setCreateBusy(true);

        try {
            const ticket = await apiRequest("/tickets", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    title: elements.createTitle.value.trim(),
                    description: elements.createDescription.value.trim(),
                    category_id: Number(elements.createCategory.value),
                    priority_id: Number(elements.createPriority.value),
                }),
            });

            elements.createForm.reset();
            closeCreateForm();

            elements.portalMessage.textContent = ticket?.ticket_code
                ? `Đã tạo ticket ${ticket.ticket_code} thành công.`
                : "Đã tạo ticket thành công.";
            elements.portalMessage.hidden = false;

            listState.page = 1;
            await loadTickets();
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

        elements.createSubmit.textContent = busy
            ? "Đang gửi..."
            : "Gửi yêu cầu";
    }

    function showCreateError(message) {
        elements.createError.textContent = message;
        elements.createError.hidden = false;
    }

    function clearCreateError() {
        elements.createError.textContent = "";
        elements.createError.hidden = true;
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
            if (payload.data.user) {
            sessionStorage.setItem(
                STORAGE_KEYS.user,
                JSON.stringify(payload.data.user),
            );
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