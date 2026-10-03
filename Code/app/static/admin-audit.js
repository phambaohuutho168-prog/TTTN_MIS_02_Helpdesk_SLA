"use strict";

(() => {
    const API_PREFIX = "/api/v1";

    const STORAGE_KEYS = Object.freeze({
        accessToken: "helpdesk.dashboard.accessToken",
        refreshToken: "helpdesk.dashboard.refreshToken",
        user: "helpdesk.dashboard.user",
    });

    const ACTION_LABELS = Object.freeze({
        USER_CREATED: "Tạo tài khoản",
        USER_UPDATED: "Cập nhật tài khoản",
        USER_ROLE_ASSIGNED: "Cấp vai trò",
        USER_ROLE_REVOKED: "Thu hồi vai trò",
        CATEGORY_CREATED: "Tạo danh mục",
        CATEGORY_UPDATED: "Cập nhật danh mục",
        PRIORITY_CREATED: "Tạo mức ưu tiên",
        PRIORITY_UPDATED: "Cập nhật mức ưu tiên",
        TICKET_CREATED: "Tạo ticket",
        TICKET_ASSIGNED: "Phân công ticket",
        TICKET_REASSIGNED: "Phân công lại ticket",
        TICKET_STARTED: "Bắt đầu xử lý",
        TICKET_INFO_REQUESTED: "Yêu cầu bổ sung",
        TICKET_INFO_PROVIDED: "Bổ sung thông tin",
        TICKET_RESOLVED: "Giải quyết ticket",
        TICKET_CLOSED: "Đóng ticket",
        TICKET_REOPENED: "Mở lại ticket",
        TICKET_RESUMED: "Tiếp tục xử lý",
        TICKET_REJECTED: "Từ chối ticket",
        TICKET_RATED: "Đánh giá ticket",
        COMMENT_CREATED: "Thêm trao đổi",
        COMMENT_UPDATED: "Sửa trao đổi",
        ATTACHMENT_UPLOADED: "Tải tệp lên",
        ATTACHMENT_DELETED: "Xóa tệp",
        LOGIN_SUCCEEDED: "Đăng nhập thành công",
        LOGIN_FAILED: "Đăng nhập thất bại",
        LOGOUT_SUCCEEDED: "Đăng xuất thành công",
        ROLE_ASSIGNED: "Cấp vai trò",
        ROLE_REMOVED: "Thu hồi vai trò",
        SLA_RUNTIME_CREATED: "Khởi tạo theo dõi SLA",
        SLA_COMPLETED: "Hoàn tất theo dõi SLA",
        SLA_WARNING_TRIGGERED: "Kích hoạt cảnh báo SLA",
        SLA_BREACH_TRIGGERED: "Ghi nhận vi phạm SLA",
        SLA_ESCALATION_TRIGGERED: "Kích hoạt chuyển cấp SLA",
        TICKET_AUTO_CLOSED: "Tự động đóng ticket",
    });

    const auditState = {
        started: false,
        page: 1,
        pageSize: 20,
        totalPages: 0,
        total: 0,
        items: [],
        filters: {},
    };

    const elements = {};

    window.addEventListener(
        "admin:authenticated",
        startAuditWorkspace,
    );

    function startAuditWorkspace() {
        if (auditState.started) return;

        auditState.started = true;
        cacheElements();

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
        elements.detailClose.addEventListener(
            "click",
            closeAuditDetail,
        );
        elements.detailDialog.addEventListener(
            "click",
            handleDialogBackdrop,
        );

        loadAuditLogs();
    }

    function cacheElements() {
        elements.total = document.getElementById("audit-total");
        elements.filterForm =
            document.getElementById("audit-filter-form");
        elements.filterActor =
            document.getElementById("audit-filter-actor");
        elements.filterTicket =
            document.getElementById("audit-filter-ticket");
        elements.filterAction =
            document.getElementById("audit-filter-action");
        elements.filterEntityType = document.getElementById(
            "audit-filter-entity-type",
        );
        elements.filterFrom =
            document.getElementById("audit-filter-from");
        elements.filterTo =
            document.getElementById("audit-filter-to");
        elements.pageSize =
            document.getElementById("audit-page-size");
        elements.filterSubmit =
            document.getElementById("audit-filter-submit");
        elements.filterReset =
            document.getElementById("audit-filter-reset");

        elements.summary =
            document.getElementById("audit-summary");
        elements.loading =
            document.getElementById("audit-list-loading");
        elements.listError =
            document.getElementById("audit-list-error");
        elements.empty =
            document.getElementById("audit-list-empty");
        elements.tableWrapper =
            document.getElementById("audit-table-wrapper");
        elements.tableBody =
            document.getElementById("audit-table-body");

        elements.pagination =
            document.getElementById("audit-pagination");
        elements.pagePrevious =
            document.getElementById("audit-page-previous");
        elements.pageNext =
            document.getElementById("audit-page-next");
        elements.pageInformation = document.getElementById(
            "audit-page-information",
        );

        elements.detailDialog =
            document.getElementById("audit-detail-dialog");
        elements.detailClose =
            document.getElementById("audit-detail-close");
        elements.detailError =
            document.getElementById("audit-detail-error");
        elements.detailTitle =
            document.getElementById("audit-detail-title");
        elements.detailId =
            document.getElementById("audit-detail-id");
        elements.detailCreatedAt = document.getElementById(
            "audit-detail-created-at",
        );
        elements.detailAction =
            document.getElementById("audit-detail-action");
        elements.detailEntity =
            document.getElementById("audit-detail-entity");
        elements.detailActor =
            document.getElementById("audit-detail-actor");
        elements.detailTicket =
            document.getElementById("audit-detail-ticket");
        elements.detailIp =
            document.getElementById("audit-detail-ip");
        elements.detailRequestId = document.getElementById(
            "audit-detail-request-id",
        );
        elements.detailReason =
            document.getElementById("audit-detail-reason");
        elements.detailOldValue = document.getElementById(
            "audit-detail-old-value",
        );
        elements.detailNewValue = document.getElementById(
            "audit-detail-new-value",
        );
    }

    async function handleFilterSubmit(event) {
        event.preventDefault();

        try {
            auditState.filters = readFilters();
            auditState.page = 1;
            auditState.pageSize = Number(
                elements.pageSize.value,
            );

            await loadAuditLogs();
        } catch (error) {
            showListError(error.message);
        }
    }

    function readFilters() {
        const createdFrom = toIsoDate(elements.filterFrom.value);
        const createdTo = toIsoDate(elements.filterTo.value);

        if (
            createdFrom &&
            createdTo &&
            new Date(createdFrom) > new Date(createdTo)
        ) {
            throw new Error(
                "Thời điểm bắt đầu phải trước thời điểm kết thúc.",
            );
        }

        return {
            actor_user_id: positiveValue(
                elements.filterActor.value,
            ),
            ticket_id: positiveValue(
                elements.filterTicket.value,
            ),
            action_code:
                elements.filterAction.value.trim().toUpperCase(),
            entity_type:
                elements.filterEntityType.value
                    .trim()
                    .toUpperCase(),
            created_from: createdFrom,
            created_to: createdTo,
        };
    }

    function positiveValue(value) {
        const normalized = String(value).trim();

        if (!normalized) return "";

        const number = Number(normalized);

        if (!Number.isInteger(number) || number <= 0) {
            throw new Error(
                "Các trường ID phải là số nguyên lớn hơn 0.",
            );
        }

        return String(number);
    }

    function toIsoDate(value) {
        if (!value) return "";

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) {
            throw new Error("Thời gian lọc không hợp lệ.");
        }

        return date.toISOString();
    }

    function resetFilters() {
        elements.filterForm.reset();

        auditState.filters = {};
        auditState.page = 1;
        auditState.pageSize = 20;
        elements.pageSize.value = "20";

        loadAuditLogs();
    }

    async function showPreviousPage() {
        if (auditState.page <= 1) return;

        auditState.page -= 1;
        await loadAuditLogs();
    }

    async function showNextPage() {
        if (auditState.page >= auditState.totalPages) return;

        auditState.page += 1;
        await loadAuditLogs();
    }

    async function loadAuditLogs() {
        setListLoading(true);
        hideListError();

        try {
            const query = buildAuditQuery();
            const pageData = await apiRequest(
                `/admin/audit-logs?${query.toString()}`,
            );

            auditState.items = pageData?.items || [];
            auditState.page = pageData?.page || 1;
            auditState.pageSize =
                pageData?.page_size || auditState.pageSize;
            auditState.total = pageData?.total || 0;
            auditState.totalPages = pageData?.total_pages || 0;

            renderAuditLogs();
        } catch (error) {
            auditState.items = [];
            showListError(error.message);
        } finally {
            setListLoading(false);
        }
    }

    function buildAuditQuery() {
        const query = new URLSearchParams();

        query.set("page", String(auditState.page));
        query.set("page_size", String(auditState.pageSize));

        for (const [key, value] of Object.entries(
            auditState.filters,
        )) {
            if (value !== "") {
                query.set(key, value);
            }
        }

        return query;
    }

    function renderAuditLogs() {
        elements.tableBody.replaceChildren();

        elements.total.textContent =
            `${auditState.total} bản ghi`;

        if (auditState.items.length === 0) {
            elements.summary.textContent =
                "Không có bản ghi phù hợp.";
            elements.empty.hidden = false;
            elements.tableWrapper.hidden = true;
            elements.pagination.hidden = true;
            return;
        }

        const fragment = document.createDocumentFragment();

        for (const audit of auditState.items) {
            fragment.append(createAuditRow(audit));
        }

        elements.tableBody.append(fragment);
        elements.empty.hidden = true;
        elements.tableWrapper.hidden = false;

        const firstItem =
            (auditState.page - 1) * auditState.pageSize + 1;
        const lastItem = Math.min(
            firstItem + auditState.items.length - 1,
            auditState.total,
        );

        elements.summary.textContent =
            `Hiển thị ${firstItem}–${lastItem} ` +
            `trên ${auditState.total} bản ghi.`;

        renderPagination();
    }

    function createAuditRow(audit) {
        const row = document.createElement("tr");

        const createdAtCell = document.createElement("td");
        createdAtCell.textContent = formatDateTime(
            audit.created_at,
        );

        const actionCell = document.createElement("td");
        const actionLabel = document.createElement("strong");
        actionLabel.textContent = actionName(audit.action_code);

        const actionCode = document.createElement("span");
        actionCode.className = "audit-secondary";
        actionCode.textContent = audit.action_code;

        actionCell.append(actionLabel, actionCode);

        const entityCell = document.createElement("td");
        const entity = document.createElement("span");
        entity.className = "audit-entity";
        entity.textContent = audit.entity_type || "—";

        const entityId = document.createElement("span");
        entityId.className = "audit-secondary";
        entityId.textContent = audit.entity_id
            ? `ID #${audit.entity_id}`
            : "Không có ID";

        entityCell.append(entity, entityId);

        const actorCell = document.createElement("td");
        actorCell.textContent = audit.actor_user_id
            ? `#${audit.actor_user_id}`
            : "Hệ thống";

        const ticketCell = document.createElement("td");
        ticketCell.textContent = audit.ticket_id
            ? `#${audit.ticket_id}`
            : "—";

        const actionButtonCell = document.createElement("td");
        const detailButton = document.createElement("button");
        detailButton.type = "button";
        detailButton.className =
            "button button--secondary audit-detail-button";
        detailButton.textContent = "Xem chi tiết";
        detailButton.addEventListener("click", () => {
            openAuditDetail(audit);
        });
        actionButtonCell.append(detailButton);

        row.append(
            createdAtCell,
            actionCell,
            entityCell,
            actorCell,
            ticketCell,
            actionButtonCell,
        );

        return row;
    }

    function renderPagination() {
        const hasMultiplePages = auditState.totalPages > 1;

        elements.pagination.hidden = !hasMultiplePages;
        elements.pagePrevious.disabled = auditState.page <= 1;
        elements.pageNext.disabled =
            auditState.page >= auditState.totalPages;
        elements.pageInformation.textContent =
            `Trang ${auditState.page}/${auditState.totalPages}`;
    }

    function openAuditDetail(audit) {
        elements.detailError.hidden = true;
        elements.detailTitle.textContent =
            `Bản ghi #${audit.audit_id}`;
        elements.detailId.textContent =
            String(audit.audit_id);
        elements.detailCreatedAt.textContent =
            formatDateTime(audit.created_at);
        elements.detailAction.textContent =
            `${actionName(audit.action_code)} ` +
            `(${audit.action_code})`;
        elements.detailEntity.textContent =
            audit.entity_id
                ? `${audit.entity_type} #${audit.entity_id}`
                : audit.entity_type;
        elements.detailActor.textContent =
            audit.actor_user_id
                ? `Người dùng #${audit.actor_user_id}`
                : "Hệ thống";
        elements.detailTicket.textContent =
            audit.ticket_id
                ? `Ticket #${audit.ticket_id}`
                : "Không liên kết ticket";
        elements.detailIp.textContent =
            audit.ip_address || "Không ghi nhận";
        elements.detailRequestId.textContent =
            audit.request_id || "Không ghi nhận";
        elements.detailReason.textContent =
            audit.reason || "Không có lý do được ghi nhận.";
        elements.detailOldValue.textContent =
            formatJson(audit.old_value_json);
        elements.detailNewValue.textContent =
            formatJson(audit.new_value_json);

        if (typeof elements.detailDialog.showModal === "function") {
            elements.detailDialog.showModal();
        } else {
            elements.detailDialog.setAttribute("open", "");
        }
    }

    function closeAuditDetail() {
        if (typeof elements.detailDialog.close === "function") {
            elements.detailDialog.close();
        } else {
            elements.detailDialog.removeAttribute("open");
        }
    }

    function handleDialogBackdrop(event) {
        if (event.target === elements.detailDialog) {
            closeAuditDetail();
        }
    }

    function formatJson(value) {
        if (value == null) return "Không có dữ liệu";

        try {
            return JSON.stringify(value, null, 2);
        } catch (_error) {
            return String(value);
        }
    }

    function actionName(actionCode) {
         return (
            ACTION_LABELS[actionCode] ||
            String(actionCode || "Không xác định")
        );
    }

    function formatDateTime(value) {
        if (!value) return "—";

        const date = new Date(value);

        if (Number.isNaN(date.getTime())) return value;

        return new Intl.DateTimeFormat("vi-VN", {
            dateStyle: "short",
            timeStyle: "medium",
        }).format(date);
    }

    function setListLoading(loading) {
        elements.loading.hidden = !loading;
        elements.filterSubmit.disabled = loading;
        elements.filterReset.disabled = loading;

        if (loading) {
            elements.empty.hidden = true;
            elements.tableWrapper.hidden = true;
            elements.pagination.hidden = true;
        }
    }

    function showListError(message) {
        elements.listError.textContent = message;
        elements.listError.hidden = false;
        elements.summary.textContent =
            "Không thể tải nhật ký kiểm toán.";
    }

    function hideListError() {
        elements.listError.textContent = "";
        elements.listError.hidden = true;
    }

    async function apiRequest(path, options = {}, allowRefresh = true) {
        const headers = new Headers(options.headers || {});
        const accessToken = sessionStorage.getItem(
            STORAGE_KEYS.accessToken,
        );

        headers.set("Accept", "application/json");

        if (accessToken) {
            headers.set("Authorization", `Bearer ${accessToken}`);
        }

        const response = await fetch(`${API_PREFIX}${path}`, {
            ...options,
            headers,
        });

        if (
            response.status === 401 &&
            allowRefresh &&
            await refreshSession()
        ) {
            return apiRequest(path, options, false);
        }

        const payload = await parseResponse(response);

        if (!response.ok) {
            if (response.status === 401) {
                clearStoredSession();
                window.location.href = "/portal";
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

    async function refreshSession() {
        const refreshToken = sessionStorage.getItem(
            STORAGE_KEYS.refreshToken,
        );

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

            if (!response.ok || !payload?.data?.access_token) {
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

        if (!contentType.includes("application/json")) return null;

        try {
            return await response.json();
        } catch (_error) {
            return null;
        }
    }

    function errorMessage(payload, fallback) {
        if (payload?.errors?.[0]?.message) {
            const field = payload.errors[0].field
                ? `${payload.errors[0].field}: `
                : "";

            return `${payload.message || ""} ${field}${payload.errors[0].message}`.trim();
        }

        if (payload?.message) return payload.message;
        if (typeof payload?.detail === "string") {
            return payload.detail;
        }

        return fallback;
    }
})();