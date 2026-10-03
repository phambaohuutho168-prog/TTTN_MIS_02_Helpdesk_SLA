"use strict";

(() => {
    const API_PREFIX = "/api/v1";

    const COMMENT_EDIT_WINDOW_MINUTES = 15;

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
        detailTicketId: null,
        workflowAction: null,
        detailTicket: null,
    };

    const WORKFLOW_ACTIONS = Object.freeze({
        START: {
            label: "Bắt đầu xử lý",
            endpoint: "start",
            payloadKey: "reason",
            inputLabel: "Ghi chú bắt đầu xử lý",
            help: "Không bắt buộc. Tối đa 1.000 ký tự.",
            required: false,
            minLength: 0,
            maxLength: 1000,
            buttonClass: "button--primary",
            successMessage: "Đã bắt đầu xử lý ticket.",
        },
        REQUEST_INFO: {
            label: "Yêu cầu bổ sung",
            endpoint: "request-info",
            payloadKey: "content",
            inputLabel: "Thông tin cần bổ sung",
            help: "Nêu rõ nội dung người gửi cần cung cấp.",
            required: true,
            minLength: 1,
            maxLength: 4000,
            buttonClass: "button--warning",
            successMessage: "Đã gửi yêu cầu bổ sung thông tin.",
        },
        RESOLVE: {
            label: "Hoàn tất xử lý",
            endpoint: "resolve",
            payloadKey: "resolution_note",
            inputLabel: "Kết quả xử lý",
            help: "Mô tả cách xử lý, tối thiểu 5 ký tự.",
            required: true,
            minLength: 5,
            maxLength: 8000,
            buttonClass: "button--success",
            successMessage: "Đã ghi nhận kết quả xử lý.",
        },
        RESUME: {
            label: "Tiếp tục xử lý",
            endpoint: "resume",
            payloadKey: "reason",
            inputLabel: "Ghi chú tiếp tục xử lý",
            help: "Không bắt buộc. SLA xử lý mới sẽ được khởi tạo.",
            required: false,
            minLength: 0,
            maxLength: 1000,
            buttonClass: "button--primary",
            successMessage: "Đã tiếp tục xử lý ticket.",
        },
        PROVIDE_INFO: {
            label: "Bổ sung thông tin",
            endpoint: "provide-info",
            payloadKey: "content",
            inputLabel: "Thông tin bổ sung",
            help: "Cung cấp nội dung mà bộ phận xử lý yêu cầu.",
            required: true,
            minLength: 1,
            maxLength: 4000,
            buttonClass: "button--primary",
            successMessage: "Đã bổ sung thông tin cho ticket.",
        },
        CLOSE: {
            label: "Xác nhận đóng ticket",
            endpoint: "close",
            payloadKey: "reason",
            inputLabel: "Ghi chú đóng ticket",
            help: "Không bắt buộc đối với Người gửi yêu cầu.",
            required: false,
            minLength: 0,
            maxLength: 1000,
            buttonClass: "button--success",
            successMessage: "Đã đóng ticket thành công.",
        },
        REOPEN: {
            label: "Mở lại ticket",
            endpoint: "reopen",
            payloadKey: "reason",
            inputLabel: "Lý do mở lại",
            help: "Nêu rõ vấn đề chưa được giải quyết, tối thiểu 5 ký tự.",
            required: true,
            minLength: 5,
            maxLength: 2000,
            buttonClass: "button--warning",
            successMessage: "Đã mở lại ticket.",
        },
    });

    const elements = {};

    document.addEventListener("DOMContentLoaded", initialize);
    window.addEventListener(
        "portal:authenticated",
        startTicketWorkspace
    );
    window.addEventListener(
        "portal:open-ticket",
        handleOpenTicketRequest,
    );

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
        elements.assignmentForm.addEventListener("submit",handleTicketAssignment,);
        elements.workflowForm.addEventListener("submit",handleWorkflowSubmit,);
        elements.workflowCancel.addEventListener("click",closeWorkflowForm,);
        elements.commentForm.addEventListener("submit",handleCommentSubmit,);
        elements.attachmentForm.addEventListener("submit",handleAttachmentUpload,);
        elements.ratingForm.addEventListener("submit",handleRatingSubmit,);

        elements.historyReload.addEventListener("click", () => {
        if (listState.detailTicket) {
            void loadTicketHistory(listState.detailTicket);
        }
    });
        elements.slaReload.addEventListener("click", handleTicketSlaReload,);
    }

    function handleOpenTicketRequest(event) {
        const ticketId = Number(event.detail?.ticketId);

        if (!Number.isInteger(ticketId) || ticketId <= 0) {
            return;
        }

        void openTicketDetail(ticketId);
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
        elements.assignmentSection = document.getElementById("ticket-assignment-section",);
        elements.assignmentForm = document.getElementById("ticket-assignment-form",);
        elements.assignmentAssignee = document.getElementById("ticket-assignment-assignee",);
        elements.assignmentReason = document.getElementById("ticket-assignment-reason",);
        elements.assignmentSubmit = document.getElementById("ticket-assignment-submit",);
        elements.assignmentError = document.getElementById("ticket-assignment-error",);
        elements.workflowSection = document.getElementById("ticket-workflow-section",);
        elements.workflowTitle = document.getElementById("ticket-workflow-title",);
        elements.workflowForm = document.getElementById("ticket-workflow-form",);
        elements.workflowError = document.getElementById("ticket-workflow-error",);
        elements.workflowInputLabel = document.getElementById("ticket-workflow-input-label",);
        elements.workflowInput = document.getElementById("ticket-workflow-input",);
        elements.workflowHelp = document.getElementById("ticket-workflow-help",);
        elements.workflowSubmit = document.getElementById("ticket-workflow-submit",);
        elements.workflowCancel = document.getElementById("ticket-workflow-cancel",);
        elements.conversationLoading = document.getElementById("ticket-conversation-loading",);
        elements.conversationError = document.getElementById("ticket-conversation-error",);
        elements.conversationEmpty = document.getElementById("ticket-conversation-empty",);
        elements.conversationList = document.getElementById("ticket-conversation-list",);
        elements.commentForm = document.getElementById("ticket-comment-form",);
        elements.commentError = document.getElementById("ticket-comment-error",);
        elements.commentContent = document.getElementById("ticket-comment-content",);
        elements.commentVisibilityGroup = document.getElementById("ticket-comment-visibility-group",);
        elements.commentVisibility = document.getElementById("ticket-comment-visibility",);
        elements.commentSubmit = document.getElementById("ticket-comment-submit",);
        elements.attachmentsEmpty = document.getElementById("ticket-attachments-empty",);
        elements.attachmentsList = document.getElementById("ticket-attachments-list",);
        elements.attachmentForm = document.getElementById("ticket-attachment-form",);
        elements.attachmentError = document.getElementById("ticket-attachment-error",);
        elements.attachmentFile = document.getElementById("ticket-attachment-file",);
        elements.attachmentSubmit = document.getElementById("ticket-attachment-submit",);
        elements.ratingSection = document.getElementById("ticket-rating-section",);
        elements.ratingLoading = document.getElementById("ticket-rating-loading",);
        elements.ratingError = document.getElementById("ticket-rating-error",);
        elements.ratingEmpty = document.getElementById("ticket-rating-empty",);
        elements.ratingResult = document.getElementById("ticket-rating-result",);
        elements.ratingResultStars = document.getElementById("ticket-rating-result-stars",);
        elements.ratingResultScore = document.getElementById("ticket-rating-result-score",);
        elements.ratingResultComment = document.getElementById("ticket-rating-result-comment",);
        elements.ratingResultAuthor = document.getElementById("ticket-rating-result-author",);
        elements.ratingResultCreatedAt = document.getElementById("ticket-rating-result-created-at",);
        elements.ratingForm = document.getElementById("ticket-rating-form",);
        elements.ratingComment = document.getElementById("ticket-rating-comment",);
        elements.ratingSubmit = document.getElementById("ticket-rating-submit",);
        elements.historyReload = document.getElementById("ticket-history-reload",);
        elements.historySummary = document.getElementById("ticket-history-summary",);
        elements.historyLoading = document.getElementById("ticket-history-loading",);
        elements.historyError = document.getElementById("ticket-history-error",);
        elements.historyEmpty = document.getElementById("ticket-history-empty",);
        elements.historyTimeline = document.getElementById("ticket-history-timeline",);
        elements.slaSection = document.getElementById("ticket-sla-section");
        elements.slaOverall = document.getElementById("ticket-sla-overall");
        elements.slaReload = document.getElementById("ticket-sla-reload");
        elements.slaLoading = document.getElementById("ticket-sla-loading");
        elements.slaError = document.getElementById("ticket-sla-error");
        elements.slaContent = document.getElementById("ticket-sla-content");
        elements.slaFirstResponse = document.getElementById("ticket-sla-first-response");
        elements.slaResponseEmpty = document.getElementById("ticket-sla-response-empty");
        elements.slaResponseContainer = document.getElementById("ticket-sla-response-container");
        elements.slaResolutionEmpty = document.getElementById("ticket-sla-resolution-empty");
        elements.slaResolutionList = document.getElementById("ticket-sla-resolution-list");
    }

    async function handleTicketSlaReload() {
        if (!listState.detailTicket) return;

        await loadTicketSla(listState.detailTicket);
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
        if (!value) return "—";
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
                throw new Error(
                    "Không nhận được dữ liệu chi tiết ticket.",
                );
            }

            listState.detailTicketId = ticket.ticket_id;
            listState.detailTicket = ticket;

            renderTicketDetail(ticket);
            configureWorkflowSection(ticket);

            await Promise.all([
                configureAssignmentSection(ticket),
                loadTicketComments(ticket),
                loadTicketRating(ticket),
                loadTicketHistory(ticket),
                loadTicketSla(ticket),
            ]);
        } catch (error) {
            console.error("OPEN_TICKET_DETAIL_ERROR", error);
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
        listState.detailTicketId = null;
        elements.assignmentSection.hidden = true;
        elements.assignmentForm.reset();
        clearAssignmentError();
        elements.workflowSection.hidden = true;
        closeWorkflowForm();
        listState.detailTicket = null;
        resetConversation();
        resetTicketAttachments();
        resetTicketRating();
        resetTicketHistory();
        resetTicketSla();
    }

    function renderTicketDetail(ticket) {
        elements.detailCode.textContent = ticket.ticket_code;
        elements.detailTitle.textContent = ticket.title;
        elements.detailCategory.textContent = ticket.category.category_name;
        elements.detailRequester.textContent =`${ticket.requester.full_name} (${ticket.requester.email})`;
        elements.detailAssignee.textContent = ticket.current_assignee?.full_name || "Chưa phân công";
        elements.detailCreatedAt.textContent = formatDateTime(ticket.created_at);
        elements.detailUpdatedAt.textContent = formatDateTime(ticket.updated_at);
        elements.detailDescription.textContent = ticket.description;

        const priorityCode = ticket.priority.priority_code.toLowerCase();

        elements.detailPriority.className = `priority-badge priority-badge--${priorityCode}`;
        elements.detailPriority.textContent = `${ticket.priority.priority_code} · ${ticket.priority.priority_name}`;

        const statusClass = ticket.status.status_code
            .toLowerCase()
            .replaceAll("_", "-");

        elements.detailStatus.className = `status-badge status-badge--${statusClass}`;
        elements.detailStatus.textContent = ticket.status.status_name;

        const responseSla = ticket.sla_summary?.response_sla;
        const resolutionCycles =
            ticket.sla_summary?.resolution_cycles || [];
        const resolutionSla =
            resolutionCycles.length > 0
                ? resolutionCycles[resolutionCycles.length - 1]
                : null;

        elements.detailResponseDeadline.textContent = formatSlaItem(responseSla);
        elements.detailResolutionDeadline.textContent = formatSlaItem(resolutionSla);

        elements.detailLoading.hidden = true;
        elements.detailError.hidden = true;

        renderTicketAttachments(ticket);

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

    const HISTORY_STATUS_LABELS = Object.freeze({
        NEW: "Mới",
        ASSIGNED: "Đã phân công",
        IN_PROGRESS: "Đang xử lý",
        WAITING_REQUESTER: "Chờ bổ sung",
        RESOLVED: "Đã giải quyết",
        CLOSED: "Đã đóng",
        REOPENED: "Đã mở lại",
        REJECTED: "Đã từ chối",
        PENDING_INFO: "Chờ bổ sung thông tin",
    });

    function resetTicketHistory() {
        elements.historyReload.disabled = false;
        elements.historySummary.textContent =
            "Chưa tải lịch sử xử lý.";
        elements.historyLoading.hidden = true;
        elements.historyError.hidden = true;
        elements.historyError.textContent = "";
        elements.historyEmpty.hidden = true;
        elements.historyTimeline.hidden = true;
        elements.historyTimeline.replaceChildren();
    }

    async function loadTicketHistory(ticket) {
        resetTicketHistory();

        elements.historyReload.disabled = true;
        elements.historyLoading.hidden = false;
        elements.historySummary.textContent =
            "Đang tải lịch sử xử lý...";

        try {
            const [statusHistory, assignments] = await Promise.all([
                fetchAllHistoryPages(
                    `/tickets/${ticket.ticket_id}/status-history`,
                ),
                fetchAllHistoryPages(
                    `/tickets/${ticket.ticket_id}/assignments`,
                ),
            ]);

            renderTicketHistory(statusHistory, assignments);
        } catch (error) {
            elements.historyError.textContent = error.message;
            elements.historyError.hidden = false;
            elements.historySummary.textContent =
                "Không thể tải lịch sử xử lý.";
        } finally {
            elements.historyLoading.hidden = true;
            elements.historyReload.disabled = false;
        }
    }

    async function fetchAllHistoryPages(path) {
        const items = [];
        let page = 1;
        let totalPages = 1;

        do {
            const separator = path.includes("?") ? "&" : "?";
            const pageData = await apiRequest(
                `${path}${separator}page=${page}&page_size=100`,
            );

            items.push(...(pageData?.items || []));
            totalPages = Math.max(pageData?.total_pages || 0, 1);
            page += 1;
        } while (page <= totalPages);

        return items;
    }

    function renderTicketHistory(statusHistory, assignments) {
        const events = [
            ...statusHistory.map(statusHistoryEvent),
            ...assignments.map(assignmentHistoryEvent),
        ].sort(
            (first, second) =>
                new Date(second.occurredAt) -
                new Date(first.occurredAt),
        );

        elements.historyTimeline.replaceChildren();

        elements.historySummary.textContent =
            `${statusHistory.length} thay đổi trạng thái · ` +
            `${assignments.length} lượt phân công`;

        if (events.length === 0) {
            elements.historyEmpty.hidden = false;
            elements.historyTimeline.hidden = true;
            return;
        }

        const fragment = document.createDocumentFragment();

        for (const event of events) {
            fragment.append(createHistoryItem(event));
        }

        elements.historyTimeline.append(fragment);
        elements.historyEmpty.hidden = true;
        elements.historyTimeline.hidden = false;
    }

    function statusHistoryEvent(history) {
        const fromStatus = history.from_status_code
            ? statusHistoryLabel(history.from_status_code)
            : null;
        const toStatus = statusHistoryLabel(
            history.to_status_code,
        );
        const actor = history.changed_by?.full_name || "Hệ thống";

        return {
            kind: "status",
            occurredAt: history.changed_at,
            title: fromStatus
                ? `${fromStatus} → ${toStatus}`
                : `Khởi tạo trạng thái ${toStatus}`,
            description: `${actor} thực hiện thay đổi trạng thái.`,
            reason: history.reason,
        };
    }

    function assignmentHistoryEvent(assignment) {
        const assignee =
            assignment.assignee?.full_name || "Không xác định";
        const assignedBy =
            assignment.assigned_by?.full_name || "Hệ thống";

        const stateDescription = assignment.is_current
            ? "Đang là người xử lý hiện tại."
            : assignment.ended_at
                ? `Kết thúc lúc ${formatDateTime(assignment.ended_at)}.`
                : "Đã kết thúc phân công.";

        return {
            kind: "assignment",
            occurredAt: assignment.assigned_at,
            title: `Phân công cho ${assignee}`,
            description:
                `${assignedBy} thực hiện phân công. ` +
                stateDescription,
            reason: assignment.reason,
        };
    }

    function createHistoryItem(event) {
        const item = document.createElement("li");
        const marker = document.createElement("span");
        const card = document.createElement("article");
        const header = document.createElement("header");
        const title = document.createElement("h4");
        const time = document.createElement("time");
        const description = document.createElement("p");
        const kind = document.createElement("span");

        item.className =
            `ticket-history-item ticket-history-item--${event.kind}`;
        marker.className = "ticket-history-marker";
        marker.setAttribute("aria-hidden", "true");

        card.className = "ticket-history-card";
        header.className = "ticket-history-header";
        title.className = "ticket-history-title";
        time.className = "ticket-history-time";
        description.className = "ticket-history-description";
        kind.className =
            `ticket-history-kind ticket-history-kind--${event.kind}`;

        title.textContent = event.title;
        time.textContent = formatDateTime(event.occurredAt);
        time.dateTime = event.occurredAt;
        description.textContent = event.description;
        kind.textContent =
            event.kind === "status"
                ? "Trạng thái"
                : "Phân công";

        header.append(title, time);
        card.append(header, description);

        if (event.reason) {
            const reason = document.createElement("p");
            reason.className = "ticket-history-reason";
            reason.textContent = `Lý do: ${event.reason}`;
            card.append(reason);
        }

        card.append(kind);
        item.append(marker, card);

        return item;
    }

    function statusHistoryLabel(statusCode) {
        return (
            HISTORY_STATUS_LABELS[statusCode] ||
            String(statusCode || "Không xác định")
        );
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
        async function configureAssignmentSection(ticket) {
        const canAdminister =
            (ticket.permissions || []).includes("ADMINISTER_TICKET");

        elements.assignmentSection.hidden = !canAdminister;

        if (!canAdminister) return;

        elements.assignmentForm.reset();
        clearAssignmentError();
        setAssignmentBusy(true);

        try {
            const users = await apiRequest(
                "/admin/users" +
                "?role_code=PROCESSOR" +
                "&is_active=true" +
                "&page=1&page_size=100",
            );

            populateSelect(
                elements.assignmentAssignee,
                users?.items || [],
                "user_id",
                (user) => `${user.full_name} · ${user.email}`,
                "Chọn người xử lý",
            );

            if (ticket.current_assignee) {
                elements.assignmentAssignee.value =
                    String(ticket.current_assignee.user_id);
                elements.assignmentSubmit.textContent =
                    "Cập nhật phân công";
            } else {
                elements.assignmentSubmit.textContent =
                    "Xác nhận phân công";
            }
        } catch (error) {
            showAssignmentError(error.message);
        } finally {
            setAssignmentBusy(false);
        }
    }

    async function handleTicketAssignment(event) {
        event.preventDefault();
        clearAssignmentError();

        const ticketId = listState.detailTicketId;
        const assigneeId = Number(elements.assignmentAssignee.value);

        if (!ticketId) {
            showAssignmentError("Không xác định được ticket cần phân công.");
            return;
        }

        if (!Number.isInteger(assigneeId) || assigneeId <= 0) {
            showAssignmentError("Vui lòng chọn người xử lý.");
            return;
        }

        setAssignmentBusy(true);

        try {
            await apiRequest(`/tickets/${ticketId}/assignment`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    assignee_id: assigneeId,
                    reason:
                        elements.assignmentReason.value.trim() || null,
                }),
            });

            elements.portalMessage.textContent =
                "Đã phân công người xử lý thành công.";
            elements.portalMessage.hidden = false;

            closeTicketDetail();
            listState.page = 1;
            await loadTickets();
        } catch (error) {
            showAssignmentError(error.message);
        } finally {
            setAssignmentBusy(false);
        }
    }

    function setAssignmentBusy(busy) {
        elements.assignmentAssignee.disabled = busy;
        elements.assignmentReason.disabled = busy;
        elements.assignmentSubmit.disabled = busy;

        if (busy) {
            elements.assignmentSubmit.textContent = "Đang xử lý...";
        }
    }

    function showAssignmentError(message) {
        elements.assignmentError.textContent = message;
        elements.assignmentError.hidden = false;
    }

    function clearAssignmentError() {
        elements.assignmentError.textContent = "";
        elements.assignmentError.hidden = true;
    }
    function configureWorkflowSection(ticket) {
        const role = currentPrimaryRole();
        const status = ticket.status.status_code;
        const actionCodes = [];

        if (role === "ADMIN" || role === "PROCESSOR") {
            if (status === "ASSIGNED") {
                actionCodes.push("START");
            } else if (status === "IN_PROGRESS") {
                actionCodes.push("REQUEST_INFO", "RESOLVE");
            } else if (status === "REOPENED") {
                actionCodes.push("RESUME");
            }
        }
       if (role === "REQUESTER") {
            if (status === "PENDING_INFO") {
                actionCodes.push("PROVIDE_INFO");
            } else if (status === "RESOLVED") {
                actionCodes.push("CLOSE", "REOPEN");
            }
        }

        elements.detailActions.replaceChildren();
        closeWorkflowForm();

        elements.workflowSection.hidden = actionCodes.length === 0;

        for (const actionCode of actionCodes) {
            const action = WORKFLOW_ACTIONS[actionCode];
            const button = document.createElement("button");

            button.type = "button";
            button.className =
                `button ${action.buttonClass}`;
            button.textContent = action.label;
            button.addEventListener(
                "click",
                () => openWorkflowForm(actionCode),
            );

            elements.detailActions.append(button);
        }
    }

    function openWorkflowForm(actionCode) {
        const action = WORKFLOW_ACTIONS[actionCode];

        if (!action) return;

        listState.workflowAction = actionCode;
        clearWorkflowError();

        elements.workflowTitle.textContent = action.label;
        elements.workflowInputLabel.textContent = action.inputLabel;
        elements.workflowHelp.textContent = action.help;
        elements.workflowInput.required = action.required;
        elements.workflowInput.minLength = action.minLength;
        elements.workflowInput.maxLength = action.maxLength;
        elements.workflowInput.value = "";
        elements.workflowSubmit.textContent = action.label;
        elements.workflowForm.hidden = false;

        window.setTimeout(() => elements.workflowInput.focus(), 0);
    }

    function closeWorkflowForm() {
        listState.workflowAction = null;
        elements.workflowForm.reset();
        elements.workflowForm.hidden = true;
        elements.workflowTitle.textContent = "Thao tác ticket";
        clearWorkflowError();
    }

    async function handleWorkflowSubmit(event) {
        event.preventDefault();
        clearWorkflowError();

        const ticketId = listState.detailTicketId;
        const action = WORKFLOW_ACTIONS[listState.workflowAction];
        const value = elements.workflowInput.value.trim();

        if (!ticketId || !action) {
            showWorkflowError("Không xác định được thao tác workflow.");
            return;
        }

        if (action.required && value.length < action.minLength) {
            showWorkflowError(
                `Nội dung phải có ít nhất ${action.minLength} ký tự.`,
            );
            return;
        }

        const payload = {
            [action.payloadKey]: value || null,
        };

        setWorkflowBusy(true);

        try {
            const updatedTicket = await apiRequest(
                `/tickets/${ticketId}/${action.endpoint}`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(payload),
                },
            );

            elements.portalMessage.textContent = action.successMessage;
            elements.portalMessage.hidden = false;

            listState.detailTicket = updatedTicket;

            renderTicketDetail(updatedTicket);
            configureWorkflowSection(updatedTicket);

            await Promise.all([
                configureAssignmentSection(updatedTicket),
                loadTicketComments(updatedTicket),
                loadTicketRating(updatedTicket),
                loadTicketHistory(updatedTicket),
                loadTicketSla(updatedTicket),
            ]);
            await loadTickets();
        } catch (error) {
            showWorkflowError(error.message);
        } finally {
            setWorkflowBusy(false);
        }
    }

    function setWorkflowBusy(busy) {
        elements.workflowInput.disabled = busy;
        elements.workflowSubmit.disabled = busy;
        elements.workflowCancel.disabled = busy;

        for (const button of elements.detailActions.querySelectorAll("button")) {
            button.disabled = busy;
        }

        if (busy) {
            elements.workflowSubmit.textContent = "Đang xử lý...";
        }
    }

    function showWorkflowError(message) {
        elements.workflowError.textContent = message;
        elements.workflowError.hidden = false;
    }

    function clearWorkflowError() {
        elements.workflowError.textContent = "";
        elements.workflowError.hidden = true;
    }
    function resetConversation() {
        elements.conversationLoading.hidden = false;
        elements.conversationError.hidden = true;
        elements.conversationError.textContent = "";
        elements.conversationEmpty.hidden = true;
        elements.conversationList.hidden = true;
        elements.conversationList.replaceChildren();
        elements.commentForm.hidden = true;
        elements.commentForm.reset();
        clearCommentError();
    }

    async function loadTicketComments(ticket) {
        resetConversation();

        try {
            const data = await apiRequest(
                `/tickets/${ticket.ticket_id}/comments` +
                "?page=1&page_size=100",
            );

            renderComments(data?.items || []);
            configureCommentForm(ticket);
        } catch (error) {
            elements.conversationLoading.hidden = true;
            elements.conversationError.textContent = error.message;
            elements.conversationError.hidden = false;
        }
    }

    function renderComments(comments) {
        elements.conversationList.replaceChildren();

        const orderedComments = [...comments].sort(
            (left, right) =>
                new Date(left.created_at) - new Date(right.created_at),
        );

        for (const comment of orderedComments) {
            elements.conversationList.append(
                createCommentItem(comment),
            );
        }

        const hasComments = orderedComments.length > 0;

        elements.conversationLoading.hidden = true;
        elements.conversationEmpty.hidden = hasComments;
        elements.conversationList.hidden = !hasComments;
    }

    function createCommentItem(comment) {
        const item = document.createElement("li");
        const header = document.createElement("div");
        const author = document.createElement("div");
        const authorName = document.createElement("strong");
        const meta = document.createElement("span");
        const badge = document.createElement("span");
        const content = document.createElement("p");
        const actions = document.createElement("div");

        item.className = "conversation-item";

        if (comment.visibility === "INTERNAL") {
            item.classList.add("conversation-item--internal");
        }

        if (comment.comment_type === "REQUEST_INFO") {
            item.classList.add("conversation-item--request-info");
        }

        header.className = "conversation-item-header";
        author.className = "conversation-author";
        meta.className = "conversation-meta";
        badge.className = "conversation-badge";
        content.className = "conversation-content";
        actions.className = "conversation-item-actions";

        authorName.textContent = comment.author.full_name;
        meta.textContent = formatDateTime(comment.created_at);

        if (comment.updated_at) {
            meta.textContent +=
                ` · Đã chỉnh sửa ${formatDateTime(comment.updated_at)}`;
        }

        badge.textContent = commentLabel(comment);
        content.textContent = comment.content;

        author.append(authorName, meta);
        header.append(author, badge);
        item.append(header, content);

        if (canEditComment(comment)) {
            const editButton = document.createElement("button");

            editButton.type = "button";
            editButton.className =
                "button button--secondary conversation-edit-button";
            editButton.textContent = "Chỉnh sửa";

            editButton.addEventListener("click", () => {
                openCommentEditor(
                    item,
                    comment,
                    content,
                    actions,
                );
            });

            actions.append(editButton);
            item.append(actions);
        }

        return item;
    }

    function commentLabel(comment) {
        if (comment.visibility === "INTERNAL") {
            return "Nội bộ";
        }

        if (comment.comment_type === "REQUEST_INFO") {
            return "Yêu cầu bổ sung";
        }

        return "Công khai";
    }

    function currentPortalUser() {
        const value = sessionStorage.getItem(STORAGE_KEYS.user);

        if (!value) return null;

        try {
            return JSON.parse(value);
        } catch (_error) {
            return null;
        }
    }

    function isTerminalTicket(ticket) {
        return ["CLOSED", "REJECTED"].includes(
            ticket?.status?.status_code,
        );
    }

    function canEditComment(comment) {
        const ticket = listState.detailTicket;
        const user = currentPortalUser();
        const role = currentPrimaryRole();

        if (!ticket || !user || isTerminalTicket(ticket)) {
            return false;
        }

        if (role === "ADMIN") return true;

        if (Number(comment.author?.user_id) !== Number(user.user_id)) {
            return false;
        }

        const createdAt = new Date(comment.created_at);

        if (Number.isNaN(createdAt.getTime())) return false;

        const elapsedMinutes =
            (Date.now() - createdAt.getTime()) / 60_000;

        return elapsedMinutes <= COMMENT_EDIT_WINDOW_MINUTES;
    }

    function openCommentEditor(
        item,
        comment,
        contentElement,
        actionsElement,
    ) {
        const form = document.createElement("form");
        const textarea = document.createElement("textarea");
        const error = document.createElement("div");
        const formActions = document.createElement("div");
        const submitButton = document.createElement("button");
        const cancelButton = document.createElement("button");

        form.className = "conversation-edit-form";
        textarea.className = "conversation-edit-input";
        textarea.rows = 4;
        textarea.maxLength = 4000;
        textarea.required = true;
        textarea.value = comment.content;

        error.className = "alert alert--error";
        error.setAttribute("role", "alert");
        error.hidden = true;

        formActions.className = "form-actions";

        submitButton.type = "submit";
        submitButton.className = "button button--primary";
        submitButton.textContent = "Lưu thay đổi";

        cancelButton.type = "button";
        cancelButton.className = "button button--secondary";
        cancelButton.textContent = "Hủy";

        formActions.append(submitButton, cancelButton);
        form.append(error, textarea, formActions);

        contentElement.hidden = true;
        actionsElement.hidden = true;
        item.append(form);

        cancelButton.addEventListener("click", () => {
            form.remove();
            contentElement.hidden = false;
            actionsElement.hidden = false;
        });

        form.addEventListener("submit", async (event) => {
            event.preventDefault();

            const newContent = textarea.value.trim();

            error.hidden = true;
            error.textContent = "";

            if (!newContent) {
                error.textContent =
                    "Vui lòng nhập nội dung trao đổi.";
                error.hidden = false;
                return;
            }

            textarea.disabled = true;
            submitButton.disabled = true;
            cancelButton.disabled = true;
            submitButton.textContent = "Đang lưu...";

            try {
                await apiRequest(
                    `/comments/${comment.comment_id}`,
                    {
                        method: "PATCH",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({
                            content: newContent,
                        }),
                    },
                );

                elements.portalMessage.textContent =
                    "Đã cập nhật nội dung trao đổi.";
                elements.portalMessage.hidden = false;

                if (listState.detailTicket) {
                    await loadTicketComments(
                        listState.detailTicket,
                    );
                }
            } catch (requestError) {
                error.textContent = requestError.message;
                error.hidden = false;

                textarea.disabled = false;
                submitButton.disabled = false;
                cancelButton.disabled = false;
                submitButton.textContent = "Lưu thay đổi";
            }
        });

        window.setTimeout(() => {
            textarea.focus();
            textarea.setSelectionRange(
                textarea.value.length,
                textarea.value.length,
            );
        }, 0);
    }

    function configureCommentForm(ticket) {
        const permissions = new Set(ticket.permissions || []);
        const canComment = permissions.has("ADD_COMMENT");
        const canCreateInternal =
            permissions.has("VIEW_INTERNAL_COMMENTS");

        elements.commentForm.hidden = !canComment;
        elements.commentVisibilityGroup.hidden = !canCreateInternal;
        elements.commentVisibility.value = "PUBLIC";
    }

    async function handleCommentSubmit(event) {
        event.preventDefault();
        clearCommentError();

        const ticket = listState.detailTicket;
        const content = elements.commentContent.value.trim();

        if (!ticket) {
            showCommentError("Không xác định được ticket.");
            return;
        }

        if (!content) {
            showCommentError("Vui lòng nhập nội dung trao đổi.");
            return;
        }

        const visibility = elements.commentVisibilityGroup.hidden
            ? "PUBLIC"
            : elements.commentVisibility.value;

        setCommentBusy(true);

        try {
            await apiRequest(`/tickets/${ticket.ticket_id}/comments`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    content,
                    visibility,
                    comment_type:
                        visibility === "INTERNAL"
                            ? "SYSTEM_NOTE"
                            : "REPLY",
                }),
            });

            elements.commentForm.reset();
            elements.commentVisibility.value = "PUBLIC";
            elements.portalMessage.textContent =
                visibility === "INTERNAL"
                    ? "Đã thêm ghi chú nội bộ."
                    : "Đã gửi trao đổi.";

            const refreshedTicket = await apiRequest(
                `/tickets/${ticket.ticket_id}`,
            );

            listState.detailTicket = refreshedTicket;
            renderTicketDetail(refreshedTicket);
            configureWorkflowSection(refreshedTicket);

            await Promise.all([
                configureAssignmentSection(refreshedTicket),
                loadTicketComments(refreshedTicket),
            ]);

            await loadTickets();
        } catch (error) {
            showCommentError(error.message);
        } finally {
            setCommentBusy(false);
        }
    }

    function setCommentBusy(busy) {
        elements.commentContent.disabled = busy;
        elements.commentVisibility.disabled = busy;
        elements.commentSubmit.disabled = busy;
        elements.commentSubmit.textContent = busy
            ? "Đang gửi..."
            : "Gửi trao đổi";
    }

    function showCommentError(message) {
        elements.commentError.textContent = message;
        elements.commentError.hidden = false;
    }

    function clearCommentError() {
        elements.commentError.textContent = "";
        elements.commentError.hidden = true;
    }
    function resetTicketAttachments() {
        elements.attachmentsList.replaceChildren();
        elements.attachmentsList.hidden = true;
        elements.attachmentsEmpty.hidden = true;
        elements.attachmentForm.hidden = true;
        elements.attachmentForm.reset();
        clearAttachmentError();
    }

    function renderTicketAttachments(ticket) {
        const attachments = ticket.attachments || [];
        const permissions = new Set(ticket.permissions || []);
        const canUpload = permissions.has("UPLOAD_ATTACHMENT");

        elements.attachmentsList.replaceChildren();

        for (const attachment of attachments) {
            elements.attachmentsList.append(
                createAttachmentItem(attachment),
            );
        }

        const hasAttachments = attachments.length > 0;

        elements.attachmentsEmpty.hidden = hasAttachments;
        elements.attachmentsList.hidden = !hasAttachments;
        elements.attachmentForm.hidden = !canUpload;
        clearAttachmentError();
    }

    function createAttachmentItem(attachment) {
        const item = document.createElement("li");
        const info = document.createElement("div");
        const name = document.createElement("span");
        const meta = document.createElement("span");
        const actions = document.createElement("div");
        const downloadButton = document.createElement("button");

        item.className = "attachment-item";
        info.className = "attachment-info";
        name.className = "attachment-name";
        meta.className = "attachment-meta";
        actions.className = "attachment-actions";

        name.textContent = attachment.file_name;
        meta.textContent =
            `${formatFileSize(attachment.file_size)} · ` +
            formatDateTime(attachment.uploaded_at);

        downloadButton.type = "button";
        downloadButton.className = "button button--secondary";
        downloadButton.textContent = "Tải xuống";
        downloadButton.addEventListener("click", () => {
            downloadAttachment(attachment, downloadButton);
        });

        info.append(name, meta);
        actions.append(downloadButton);

        if (canDeleteAttachment(attachment)) {
            const deleteButton = document.createElement("button");

            deleteButton.type = "button";
            deleteButton.className =
                "button attachment-delete-button";
            deleteButton.textContent = "Xóa tệp";

            deleteButton.addEventListener("click", () => {
                deleteAttachment(attachment, deleteButton);
            });

            actions.append(deleteButton);
        }

        item.append(info, actions);

        return item;
    }

        function canDeleteAttachment(attachment) {
        const ticket = listState.detailTicket;
        const user = currentPortalUser();
        const role = currentPrimaryRole();

        if (!ticket || !user) return false;

        if (role === "ADMIN") return true;

        return (
            !isTerminalTicket(ticket) &&
            Number(attachment.uploaded_by) === Number(user.user_id)
        );
    }

    async function deleteAttachment(attachment, button) {
        const confirmed = window.confirm(
            `Bạn có chắc muốn xóa tệp "${attachment.file_name}" không?`,
        );

        if (!confirmed) return;

        clearAttachmentError();

        button.disabled = true;
        button.textContent = "Đang xóa...";

        try {
            await apiRequest(
                `/attachments/${attachment.attachment_id}`,
                {
                    method: "DELETE",
                },
            );

            const updatedTicket = await apiRequest(
                `/tickets/${attachment.ticket_id}`,
            );

            listState.detailTicket = updatedTicket;
            renderTicketAttachments(updatedTicket);

            elements.portalMessage.textContent =
                `Đã xóa tệp "${attachment.file_name}".`;
            elements.portalMessage.hidden = false;
        } catch (error) {
            showAttachmentError(error.message);

            button.disabled = false;
            button.textContent = "Xóa tệp";
        }
    }

    function formatFileSize(value) {
        const bytes = Number(value || 0);

        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) {
            return `${(bytes / 1024).toFixed(1)} KB`;
        }

        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    async function handleAttachmentUpload(event) {
        event.preventDefault();
        clearAttachmentError();

        const ticket = listState.detailTicket;
        const file = elements.attachmentFile.files[0];

        if (!ticket) {
            showAttachmentError("Không xác định được ticket.");
            return;
        }

        if (!file) {
            showAttachmentError("Vui lòng chọn tệp.");
            return;
        }

        if (file.size > 10 * 1024 * 1024) {
            showAttachmentError("Tệp vượt quá giới hạn 10 MB.");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);

        setAttachmentBusy(true);

        try {
            await apiRequest(
                `/tickets/${ticket.ticket_id}/attachments`,
                {
                    method: "POST",
                    body: formData,
                },
            );

            elements.portalMessage.textContent =
                "Đã tải tệp đính kèm thành công.";
            elements.portalMessage.hidden = false;

            const refreshedTicket = await apiRequest(
                `/tickets/${ticket.ticket_id}`,
            );

            listState.detailTicket = refreshedTicket;
            renderTicketDetail(refreshedTicket);
            configureWorkflowSection(refreshedTicket);

            await Promise.all([
                configureAssignmentSection(refreshedTicket),
                loadTicketComments(refreshedTicket),
            ]);
        } catch (error) {
            showAttachmentError(error.message);
        } finally {
            setAttachmentBusy(false);
        }
    }

    async function downloadAttachment(
        attachment,
        button,
        retry = true,
    ) {
        clearAttachmentError();

        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = "Đang tải...";

        try {
            const accessToken = sessionStorage.getItem(
                STORAGE_KEYS.accessToken,
            );

            const response = await fetch(
                `${API_PREFIX}/attachments/` +
                `${attachment.attachment_id}/download`,
                {
                    headers: {
                        "Authorization": `Bearer ${accessToken}`,
                    },
                },
            );

            if (response.status === 401 && retry) {
                const refreshed = await refreshSession();

                if (refreshed) {
                    button.disabled = false;
                    button.textContent = originalText;
                    await downloadAttachment(
                        attachment,
                        button,
                        false,
                    );
                    return;
                }
            }

            if (!response.ok) {
                const payload = await parseResponse(response);

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

            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);
            const link = document.createElement("a");

            link.href = objectUrl;
            link.download = attachment.file_name;
            document.body.append(link);
            link.click();
            link.remove();

            window.setTimeout(
                () => URL.revokeObjectURL(objectUrl),
                1000,
            );
        } catch (error) {
            showAttachmentError(error.message);
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    }

    function setAttachmentBusy(busy) {
        elements.attachmentFile.disabled = busy;
        elements.attachmentSubmit.disabled = busy;
        elements.attachmentSubmit.textContent = busy
            ? "Đang tải lên..."
            : "Tải tệp lên";
    }

    function showAttachmentError(message) {
        elements.attachmentError.textContent = message;
        elements.attachmentError.hidden = false;
    }

    function clearAttachmentError() {
        elements.attachmentError.textContent = "";
        elements.attachmentError.hidden = true;
    }
    function resetTicketRating() {
        elements.ratingSection.hidden = true;
        elements.ratingLoading.hidden = true;

        elements.ratingError.textContent = "";
        elements.ratingError.hidden = true;

        elements.ratingEmpty.textContent = "Ticket chưa có đánh giá.";
        elements.ratingEmpty.hidden = true;

        elements.ratingResult.hidden = true;
        elements.ratingResultStars.textContent = "";
        elements.ratingResultScore.textContent = "";
        elements.ratingResultComment.textContent = "";
        elements.ratingResultAuthor.textContent = "";
        elements.ratingResultCreatedAt.textContent = "";
        elements.ratingResultCreatedAt.removeAttribute("datetime");

        elements.ratingForm.hidden = true;
        elements.ratingForm.reset();

        setRatingBusy(false);
    }

    async function loadTicketRating(ticket) {
        resetTicketRating();

        elements.ratingSection.hidden = false;
        elements.ratingLoading.hidden = false;

        try {
            const rating = await apiRequest(
                `/tickets/${ticket.ticket_id}/rating`,
            );

            renderTicketRating(rating);
        } catch (error) {
            if (
                error.status === 404 &&
                error.code === "RATING_NOT_FOUND"
            ) {
                renderUnratedTicket(ticket);
                return;
            }

            elements.ratingLoading.hidden = true;
            showRatingError(error.message);
        }
    }

    function renderUnratedTicket(ticket) {
        const role = currentPrimaryRole();
        const status = ticket.status.status_code;
        const canRate =
            role === "REQUESTER" &&
            ["RESOLVED", "CLOSED"].includes(status);

        elements.ratingLoading.hidden = true;
        elements.ratingResult.hidden = true;
        elements.ratingEmpty.hidden = false;
        elements.ratingForm.hidden = !canRate;

        if (canRate) {
            elements.ratingEmpty.textContent =
                "Ticket chưa có đánh giá. Hãy chia sẻ trải nghiệm hỗ trợ.";
            return;
        }

        if (role === "REQUESTER") {
            elements.ratingEmpty.textContent =
                "Bạn có thể đánh giá khi ticket đã được giải quyết hoặc đóng.";
            return;
        }

        elements.ratingEmpty.textContent =
            "Người gửi yêu cầu chưa đánh giá ticket này.";
    }

    function renderTicketRating(rating) {
        const score = Number(rating.score);

        elements.ratingSection.hidden = false;
        elements.ratingLoading.hidden = true;
        elements.ratingError.hidden = true;
        elements.ratingEmpty.hidden = true;
        elements.ratingForm.hidden = true;
        elements.ratingResult.hidden = false;

        elements.ratingResultStars.textContent =
            "★".repeat(score) + "☆".repeat(5 - score);
        elements.ratingResultScore.textContent = `${score}/5`;

        elements.ratingResultComment.textContent =
            rating.comment || "Không có nhận xét.";

        elements.ratingResultAuthor.textContent =
            rating.rated_by?.full_name || "Người gửi yêu cầu";

        elements.ratingResultCreatedAt.textContent =
            formatDateTime(rating.created_at);
        elements.ratingResultCreatedAt.dateTime = rating.created_at;
    }

    async function handleRatingSubmit(event) {
        event.preventDefault();
        clearRatingError();

        const ticket = listState.detailTicket;
        const selectedScore = elements.ratingForm.querySelector(
            'input[name="ticket-rating-score"]:checked',
        );

        if (!ticket) {
            showRatingError("Không xác định được ticket.");
            return;
        }

        if (!selectedScore) {
            showRatingError("Vui lòng chọn mức đánh giá từ 1 đến 5 sao.");
            return;
        }

        const score = Number(selectedScore.value);
        const comment = elements.ratingComment.value.trim();

        setRatingBusy(true);

        try {
            const rating = await apiRequest(
                `/tickets/${ticket.ticket_id}/rating`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        score,
                        comment: comment || null,
                    }),
                },
            );

            elements.portalMessage.textContent =
                "Cảm ơn bạn đã gửi đánh giá.";
            elements.portalMessage.hidden = false;

            renderTicketRating(rating);
        } catch (error) {
            showRatingError(error.message);
        } finally {
            setRatingBusy(false);
        }
    }

    function setRatingBusy(busy) {
        for (const control of elements.ratingForm.elements) {
            control.disabled = busy;
        }

        elements.ratingSubmit.textContent = busy
            ? "Đang gửi..."
            : "Gửi đánh giá";
    }

    function showRatingError(message) {
        elements.ratingSection.hidden = false;
        elements.ratingLoading.hidden = true;
        elements.ratingError.textContent = message;
        elements.ratingError.hidden = false;
    }

    function clearRatingError() {
        elements.ratingError.textContent = "";
        elements.ratingError.hidden = true;
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

    function resetTicketSla() {
        elements.slaLoading.hidden = true;
        elements.slaError.hidden = true;
        elements.slaError.textContent = "";
        elements.slaContent.hidden = true;

        elements.slaOverall.className =
            "sla-status-badge sla-status-badge--muted";
        elements.slaOverall.textContent = "Chưa tải";

        elements.slaFirstResponse.textContent = "—";
        elements.slaResponseEmpty.hidden = true;
        elements.slaResolutionEmpty.hidden = true;

        elements.slaResponseContainer.replaceChildren();
        elements.slaResolutionList.replaceChildren();
    }

    async function loadTicketSla(ticket) {
        const ticketId = Number(ticket?.ticket_id);

        if (!ticketId) return;

        resetTicketSla();
        elements.slaLoading.hidden = false;
        elements.slaReload.disabled = true;

        try {
            const sla = await apiRequest(`/tickets/${ticketId}/sla`);

            if (listState.detailTicketId !== ticketId) return;

            renderTicketSla(sla);
        } catch (error) {
            if (listState.detailTicketId !== ticketId) return;

            elements.slaLoading.hidden = true;
            elements.slaContent.hidden = true;
            elements.slaError.textContent =
                error.message || "Không thể tải thông tin SLA.";
            elements.slaError.hidden = false;
        } finally {
            if (listState.detailTicketId === ticketId) {
                elements.slaReload.disabled = false;
            }
        }
    }

    function renderTicketSla(sla) {
        const responseSla = sla?.response_sla || null;
        const resolutionCycles = Array.isArray(sla?.resolution_cycles)
            ? [...sla.resolution_cycles]
            : [];

        resolutionCycles.sort(
            (left, right) =>
                Number(right.cycle_no || 0) -
                Number(left.cycle_no || 0),
        );

        elements.slaLoading.hidden = true;
        elements.slaError.hidden = true;
        elements.slaContent.hidden = false;

        setTicketSlaStatusBadge(
            elements.slaOverall,
            sla?.overall_status,
        );

        elements.slaFirstResponse.textContent =
            formatDateTime(sla?.first_response_at);

        elements.detailResponseDeadline.textContent =
            formatDateTime(
                responseSla?.effective_due_at ||
                responseSla?.due_at,
            );

        const currentResolution =
            resolutionCycles.find((item) =>
                ["ACTIVE", "PAUSED"].includes(item.runtime_status),
            ) ||
            resolutionCycles[0] ||
            null;

        elements.detailResolutionDeadline.textContent =
            formatDateTime(
                currentResolution?.effective_due_at ||
                currentResolution?.due_at,
            );

        elements.slaResponseContainer.replaceChildren();

        if (responseSla) {
            elements.slaResponseEmpty.hidden = true;
            elements.slaResponseContainer.append(
                createTicketSlaCard(
                    responseSla,
                    "Thời hạn phản hồi đầu tiên",
                ),
            );
        } else {
            elements.slaResponseEmpty.hidden = false;
        }

        elements.slaResolutionList.replaceChildren();

        if (resolutionCycles.length === 0) {
            elements.slaResolutionEmpty.hidden = false;
        } else {
            elements.slaResolutionEmpty.hidden = true;

            for (const cycle of resolutionCycles) {
                const item = document.createElement("li");

                item.append(
                    createTicketSlaCard(
                        cycle,
                        `Chu kỳ xử lý ${cycle.cycle_no}`,
                    ),
                );

                elements.slaResolutionList.append(item);
            }
        }
    }

    function createTicketSlaCard(item, title) {
        const card = document.createElement("article");
        const header = document.createElement("header");
        const headingGroup = document.createElement("div");
        const heading = document.createElement("h5");
        const subtitle = document.createElement("p");
        const statusBadge = document.createElement("span");
        const details = document.createElement("dl");

        card.className = "ticket-sla-card";
        header.className = "ticket-sla-card__header";
        details.className = "ticket-sla-card__grid";

        heading.textContent = title;
        subtitle.textContent =
            `Chính sách phiên bản ${item.policy_version} · ` +
            `${formatTicketSlaMinutes(item.target_minutes)}`;

        setTicketSlaStatusBadge(statusBadge, item.status);

        headingGroup.append(heading, subtitle);
        header.append(headingGroup, statusBadge);

        appendTicketSlaMetric(
            details,
            "Bắt đầu",
            formatDateTime(item.started_at),
        );
        appendTicketSlaMetric(
            details,
            "Hạn hiệu lực",
            formatDateTime(item.effective_due_at || item.due_at),
        );
        appendTicketSlaMetric(
            details,
            "Hoàn tất",
            formatDateTime(item.completed_at),
        );
        appendTicketSlaMetric(
            details,
            "Trạng thái vận hành",
            formatTicketSlaRuntime(item.runtime_status),
        );
        appendTicketSlaMetric(
            details,
            "Kết quả",
            formatTicketSlaResult(item.result),
        );
        appendTicketSlaMetric(
            details,
            "Thời gian tạm dừng",
            formatTicketSlaSeconds(item.total_paused_seconds),
        );

        card.append(header, details);

        if (item.progress_percent != null) {
            card.append(createTicketSlaProgress(item));
        }

        return card;
    }

    function appendTicketSlaMetric(container, label, value) {
        const wrapper = document.createElement("div");
        const term = document.createElement("dt");
        const description = document.createElement("dd");

        term.textContent = label;
        description.textContent = value || "—";

        wrapper.append(term, description);
        container.append(wrapper);
    }

    function createTicketSlaProgress(item) {
        const group = document.createElement("div");
        const label = document.createElement("div");
        const description = document.createElement("span");
        const percentage = document.createElement("strong");
        const progress = document.createElement("progress");

        const numericProgress = Number(item.progress_percent);
        const displayedProgress = Number.isFinite(numericProgress)
            ? Math.max(0, numericProgress)
            : 0;
        const progressValue = Math.min(100, displayedProgress);
        const tone = ticketSlaTone(item.status?.tone);

        group.className = "ticket-sla-progress-group";
        label.className = "ticket-sla-progress-label";

        description.textContent =
            formatTicketSlaRemaining(item.remaining_seconds);
        percentage.textContent =
            `${Math.round(displayedProgress)}% thời hạn`;

        progress.className = "ticket-sla-progress";

        if (["warning", "danger", "success"].includes(tone)) {
            progress.classList.add(
                `ticket-sla-progress--${tone}`,
            );
        }

        progress.max = 100;
        progress.value = progressValue;
        progress.setAttribute(
            "aria-label",
            `${titleForSlaType(item.sla_type)}: ` +
            `${Math.round(displayedProgress)}% thời hạn`,
        );

        label.append(description, percentage);
        group.append(label, progress);

        return group;
    }

    function setTicketSlaStatusBadge(element, status) {
        const tone = ticketSlaTone(status?.tone);

        element.className =
            `sla-status-badge sla-status-badge--${tone}`;
        element.textContent =
            status?.label ||
            formatTicketSlaStatus(status?.code);
    }

    function ticketSlaTone(value) {
        const tone = String(value || "MUTED").toLowerCase();

        return ["info", "warning", "danger", "success", "muted"]
            .includes(tone)
            ? tone
            : "muted";
    }

    function formatTicketSlaStatus(code) {
        const labels = {
            ON_TRACK: "Đúng tiến độ",
            NEAR_DUE: "Sắp đến hạn",
            OVERDUE: "Quá hạn",
            MET: "Đạt SLA",
            NOT_APPLICABLE: "Không áp dụng",
        };

        return labels[code] || "Chưa xác định";
    }

    function formatTicketSlaRuntime(value) {
        const labels = {
            ACTIVE: "Đang tính thời gian",
            PAUSED: "Đang tạm dừng",
            COMPLETED: "Đã hoàn tất",
            CANCELLED: "Đã hủy",
        };

        return labels[value] || value || "—";
    }

    function formatTicketSlaResult(value) {
        const labels = {
            MET: "Đạt SLA",
            BREACHED: "Vi phạm SLA",
            CANCELLED: "Đã hủy",
        };

        return labels[value] || value || "Chưa có kết quả";
    }

    function titleForSlaType(value) {
        return value === "RESPONSE" ? "SLA phản hồi" : "SLA xử lý";
    }

    function formatTicketSlaMinutes(value) {
        const minutes = Number(value);

        if (!Number.isFinite(minutes)) return "Chưa có thời hạn";

        if (minutes < 60) return `${minutes} phút`;

        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;

        return remainingMinutes
            ? `${hours} giờ ${remainingMinutes} phút`
            : `${hours} giờ`;
    }

    function formatTicketSlaSeconds(value) {
        const seconds = Number(value);

        if (!Number.isFinite(seconds) || seconds <= 0) {
            return "Không";
        }

        return formatTicketSlaDuration(seconds);
    }

    function formatTicketSlaRemaining(value) {
        const seconds = Number(value);

        if (!Number.isFinite(seconds)) {
            return "Chưa có dữ liệu thời gian";
        }

        if (seconds < 0) {
            return `Quá hạn ${formatTicketSlaDuration(Math.abs(seconds))}`;
        }

        return `Còn lại ${formatTicketSlaDuration(seconds)}`;
    }

    function formatTicketSlaDuration(value) {
        const totalMinutes = Math.max(
            0,
            Math.floor(Number(value) / 60),
        );
        const days = Math.floor(totalMinutes / 1440);
        const hours = Math.floor((totalMinutes % 1440) / 60);
        const minutes = totalMinutes % 60;
        const parts = [];

        if (days) parts.push(`${days} ngày`);
        if (hours) parts.push(`${hours} giờ`);
        if (minutes || parts.length === 0) {
            parts.push(`${minutes} phút`);
        }

        return parts.join(" ");
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