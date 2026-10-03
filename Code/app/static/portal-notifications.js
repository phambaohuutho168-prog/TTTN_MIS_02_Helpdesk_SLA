"use strict";

(() => {
    const API_PREFIX = "/api/v1";

    const STORAGE_KEYS = Object.freeze({
        accessToken: "helpdesk.dashboard.accessToken",
        refreshToken: "helpdesk.dashboard.refreshToken",
        user: "helpdesk.dashboard.user",
    });

    const NOTIFICATION_TYPE_LABELS = Object.freeze({
        TICKET_CREATED: "Ticket mới",
        TICKET_ASSIGNED: "Được phân công",
        TICKET_REASSIGNED: "Được phân công lại",
        TICKET_STARTED: "Bắt đầu xử lý",
        TICKET_IN_PROGRESS: "Đang xử lý",
        TICKET_INFO_REQUESTED: "Yêu cầu bổ sung thông tin",
        TICKET_INFO_PROVIDED: "Đã bổ sung thông tin",
        TICKET_REPLY: "Trao đổi mới",
        TICKET_RESOLVED: "Ticket đã được giải quyết",
        TICKET_CLOSED: "Ticket đã đóng",
        TICKET_AUTO_CLOSED: "Ticket tự động đóng",
        TICKET_REOPENED: "Ticket được mở lại",
        TICKET_RESUMED: "Tiếp tục xử lý",
        TICKET_REJECTED: "Ticket bị từ chối",
        TICKET_RATED: "Đánh giá mới",
        TICKET_STATUS_CHANGED: "Thay đổi trạng thái",
        SLA_NEAR_DUE: "SLA sắp đến hạn",
        SLA_OVERDUE: "SLA quá hạn",
        SLA_BREACHED: "Vi phạm SLA",
        SLA_ESCALATED: "Cảnh báo SLA",
    });
    const notificationState = {
        page: 1,
        pageSize: 10,
        totalPages: 0,
        unreadTotal: 0,
        items: [],
        loading: false,
    };

    const elements = {};

    document.addEventListener("DOMContentLoaded", initialize);

    function initialize() {
        cacheElements();

        elements.toggle.addEventListener("click", handleToggle);
        elements.filter.addEventListener("change", handleFilterChange);
        elements.markAll.addEventListener("click", handleMarkAll);
        elements.previous.addEventListener("click", handlePreviousPage);
        elements.next.addEventListener("click", handleNextPage);

        document.addEventListener("click", handleOutsideClick);
        document.addEventListener("keydown", handleKeydown);
        window.addEventListener(
            "portal:authenticated",
            handleAuthenticated,
        );

        window.setInterval(() => {
            if (sessionStorage.getItem(STORAGE_KEYS.accessToken)) {
                void loadUnreadCount();
            }
        }, 60_000);
    }

    function cacheElements() {
        const ids = {
            center: "notification-center",
            toggle: "notification-toggle",
            unreadCount: "notification-unread-count",
            panel: "notification-panel",
            filter: "notification-filter",
            markAll: "notification-mark-all",
            loading: "notification-loading",
            error: "notification-error",
            empty: "notification-empty",
            list: "notification-list",
            previous: "notification-previous",
            next: "notification-next",
            pageStatus: "notification-page-status",
        };

        for (const [name, id] of Object.entries(ids)) {
            elements[name] = document.getElementById(id);
        }
    }

    function handleAuthenticated() {
        notificationState.page = 1;
        notificationState.totalPages = 0;
        notificationState.items = [];

        closePanel();
        void loadUnreadCount();
    }

    function handleToggle(event) {
        event.stopPropagation();

        if (elements.panel.hidden) {
            openPanel();
        } else {
            closePanel();
        }
    }

    function openPanel() {
        elements.panel.hidden = false;
        elements.toggle.setAttribute("aria-expanded", "true");
        void loadNotifications();
    }

    function closePanel() {
        elements.panel.hidden = true;
        elements.toggle.setAttribute("aria-expanded", "false");
    }

    function handleOutsideClick(event) {
        if (
            !elements.panel.hidden &&
            !elements.center.contains(event.target)
        ) {
            closePanel();
        }
    }

    function handleKeydown(event) {
        if (event.key === "Escape" && !elements.panel.hidden) {
            closePanel();
            elements.toggle.focus();
        }
    }

    function handleFilterChange() {
        notificationState.page = 1;
        void loadNotifications();
    }

    async function handleMarkAll() {
        if (notificationState.loading || notificationState.unreadTotal === 0) {
            return;
        }

        elements.markAll.disabled = true;
        elements.markAll.textContent = "Đang cập nhật...";

        try {
            await apiRequest("/notifications/read-all", {
                method: "PATCH",
            });

            notificationState.page = 1;

            await Promise.all([
                loadUnreadCount(),
                loadNotifications(),
            ]);
        } catch (error) {
            showError(error.message);
        } finally {
            elements.markAll.textContent = "Đánh dấu tất cả đã đọc";
            elements.markAll.disabled =
                notificationState.unreadTotal === 0;
        }
    }

    function handlePreviousPage() {
        if (
            notificationState.loading ||
            notificationState.page <= 1
        ) {
            return;
        }

        notificationState.page -= 1;
        void loadNotifications();
    }

    function handleNextPage() {
        if (
            notificationState.loading ||
            notificationState.page >= notificationState.totalPages
        ) {
            return;
        }

        notificationState.page += 1;
        void loadNotifications();
    }

    async function handleNotificationClick(notification) {
        try {
            if (!notification.is_read) {
                const updated = await apiRequest(
                    `/notifications/${notification.notification_id}/read`,
                    {method: "PATCH"},
                );

                notification.is_read = updated.is_read;
                notification.read_at = updated.read_at;

                await loadUnreadCount();

                if (elements.filter.value === "false") {
                    await loadNotifications();
                } else {
                    renderNotifications();
                }
            }

            if (notification.ticket_id) {
                closePanel();

                window.dispatchEvent(
                    new CustomEvent("portal:open-ticket", {
                        detail: {
                            ticketId: notification.ticket_id,
                        },
                    }),
                );
            }
        } catch (error) {
            showError(error.message);
        }
    }

    async function loadUnreadCount() {
        try {
            const data = await apiRequest(
                "/notifications?is_read=false&page=1&page_size=1",
            );

            notificationState.unreadTotal = data.total;
            updateUnreadBadge(data.total);
            elements.markAll.disabled = data.total === 0;
        } catch (_error) {
            notificationState.unreadTotal = 0;
            updateUnreadBadge(0);
        }
    }

    async function loadNotifications() {
        if (notificationState.loading) return;

        setLoading(true);

        try {
            const query = new URLSearchParams({
                page: String(notificationState.page),
                page_size: String(notificationState.pageSize),
            });

            if (elements.filter.value !== "") {
                query.set("is_read", elements.filter.value);
            }

            const data = await apiRequest(
                `/notifications?${query.toString()}`,
            );

            notificationState.items = data.items;
            notificationState.totalPages = data.total_pages;

            if (
                data.total_pages > 0 &&
                notificationState.page > data.total_pages
            ) {
                notificationState.page = data.total_pages;
                setLoading(false);
                await loadNotifications();
                return;
            }

            renderNotifications();
        } catch (error) {
            showError(error.message);
        } finally {
            setLoading(false);
        }
    }

    function renderNotifications() {
        elements.list.replaceChildren();

        for (const notification of notificationState.items) {
            elements.list.append(
                createNotificationItem(notification),
            );
        }

        const hasItems = notificationState.items.length > 0;

        elements.empty.hidden = hasItems;
        elements.list.hidden = !hasItems;

        const displayedTotalPages = Math.max(
            notificationState.totalPages,
            1,
        );

        elements.pageStatus.textContent =
            `Trang ${notificationState.page}/${displayedTotalPages}`;

        elements.previous.disabled =
            notificationState.page <= 1 ||
            notificationState.loading;

        elements.next.disabled =
            notificationState.totalPages === 0 ||
            notificationState.page >= notificationState.totalPages ||
            notificationState.loading;
    }

    function createNotificationItem(notification) {
        const item = document.createElement("li");
        const button = document.createElement("button");
        const title = document.createElement("span");
        const message = document.createElement("span");
        const meta = document.createElement("span");
        const type = document.createElement("span");
        const createdAt = document.createElement("time");

        item.className = "notification-item";

        if (!notification.is_read) {
            item.classList.add("notification-item--unread");
        }

        button.type = "button";
        button.className = "notification-item__button";
        button.addEventListener(
            "click",
            () => void handleNotificationClick(notification),
        );

        title.className = "notification-item__title";
        title.textContent = notification.title;

        message.className = "notification-item__message";
        message.textContent = notification.message;

        meta.className = "notification-item__meta";

        type.textContent = notification.ticket_id
            ? `Ticket #${notification.ticket_id} · ${formatType(notification.type)}`
            : formatType(notification.type);

        createdAt.dateTime = notification.created_at;
        createdAt.textContent = formatDateTime(notification.created_at);

        meta.append(type, createdAt);
        button.append(title, message, meta);
        item.append(button);

        return item;
    }

    function formatType(value) {
        if (!value) return "Thông báo";

        const normalizedType = String(value)
            .trim()
            .toUpperCase()
            .replace(/[^A-Z0-9]+/g, "_")
            .replace(/^_+|_+$/g, "");

        if (NOTIFICATION_TYPE_LABELS[normalizedType]) {
            return NOTIFICATION_TYPE_LABELS[normalizedType];
        }

        return normalizedType
            .replaceAll("_", " ")
            .toLowerCase()
            .replace(/^./, (character) => character.toUpperCase());
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

    function setLoading(loading) {
        notificationState.loading = loading;
        elements.loading.hidden = !loading;
        elements.filter.disabled = loading;
        elements.previous.disabled = loading;
        elements.next.disabled = loading;

        if (loading) {
            elements.error.hidden = true;
            elements.empty.hidden = true;
            elements.list.hidden = true;
        }
    }

    function showError(message) {
        elements.loading.hidden = true;
        elements.empty.hidden = true;
        elements.list.hidden = true;
        elements.error.textContent = message;
        elements.error.hidden = false;
    }

    function updateUnreadBadge(total) {
        elements.unreadCount.textContent =
            total > 99 ? "99+" : String(total);
        elements.unreadCount.hidden = total === 0;
    }

    async function apiRequest(path, options = {}, allowRefresh = true) {
        const headers = new Headers(options.headers || {});
        const accessToken =
            sessionStorage.getItem(STORAGE_KEYS.accessToken);

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
            const data = payload?.data;

            if (!response.ok || !data?.access_token) {
                return false;
            }

            sessionStorage.setItem(
                STORAGE_KEYS.accessToken,
                data.access_token,
            );

            if (data.refresh_token) {
                sessionStorage.setItem(
                    STORAGE_KEYS.refreshToken,
                    data.refresh_token,
                );
            }

            if (data.user) {
                sessionStorage.setItem(
                    STORAGE_KEYS.user,
                    JSON.stringify(data.user),
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
        if (typeof payload?.detail === "string") return payload.detail;

        return fallback;
    }
})();