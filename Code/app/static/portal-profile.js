"use strict";

(() => {
    const API_PREFIX = "/api/v1";

    const STORAGE_KEYS = Object.freeze({
        accessToken: "helpdesk.dashboard.accessToken",
        refreshToken: "helpdesk.dashboard.refreshToken",
        user: "helpdesk.dashboard.user",
    });

    const ROLE_LABELS = Object.freeze({
        ADMIN: "Quản trị viên",
        PROCESSOR: "Người xử lý",
        REQUESTER: "Người gửi yêu cầu",
    });

    const elements = {};
    let currentUser = null;

    document.addEventListener("DOMContentLoaded", initialize);

    function initialize() {
        cacheElements();

        elements.open.addEventListener("click", openProfile);
        elements.close.addEventListener("click", closeProfile);
        elements.cancel.addEventListener("click", closeProfile);
        elements.dialog.addEventListener(
            "click",
            handleBackdropClick,
        );
        elements.form.addEventListener("submit", handleSubmit);

        window.addEventListener(
            "portal:authenticated",
            synchronizeStoredUser,
        );
    }

    function cacheElements() {
        const ids = {
            open: "profile-open",
            dialog: "profile-dialog",
            close: "profile-close",
            form: "profile-form",
            email: "profile-email",
            fullName: "profile-full-name",
            phone: "profile-phone",
            department: "profile-department",
            roleList: "profile-role-list",
            error: "profile-error",
            success: "profile-success",
            submit: "profile-submit",
            cancel: "profile-cancel",
        };

        for (const [name, id] of Object.entries(ids)) {
            elements[name] = document.getElementById(id);
        }
    }

    function synchronizeStoredUser() {
        currentUser = readStoredUser();
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

    function openProfile() {
        currentUser = readStoredUser();

        if (!currentUser) return;

        resetMessages();
        renderProfile(currentUser);

        if (!elements.dialog.open) {
            elements.dialog.showModal();
        }

        window.setTimeout(
            () => elements.fullName.focus(),
            0,
        );
    }

    function closeProfile() {
        if (elements.dialog.open) {
            elements.dialog.close();
        }

        resetMessages();
    }

    function handleBackdropClick(event) {
        if (event.target === elements.dialog) {
            closeProfile();
        }
    }

    function renderProfile(user) {
        elements.email.value = user.email || "";
        elements.fullName.value = user.full_name || "";
        elements.phone.value = user.phone || "";
        elements.department.value =
            user.department?.department_name ||
            "Chưa được phân phòng ban";

        elements.roleList.replaceChildren();

        for (const role of user.roles || []) {
            const badge = document.createElement("span");

            badge.className = "profile-role-badge";
            badge.textContent =
                ROLE_LABELS[role.role_code] ||
                role.role_name ||
                role.role_code;

            elements.roleList.append(badge);
        }

        if (!elements.roleList.children.length) {
            const badge = document.createElement("span");

            badge.className = "profile-role-badge";
            badge.textContent = "Chưa được cấp vai trò";
            elements.roleList.append(badge);
        }
    }

    async function handleSubmit(event) {
        event.preventDefault();
        resetMessages();

        const fullName = elements.fullName.value.trim();
        const phone = elements.phone.value.trim();

        if (!fullName) {
            showError("Họ và tên không được để trống.");
            elements.fullName.focus();
            return;
        }

        setBusy(true);

        try {
            const updatedUser = await apiRequest(
                "/users/me",
                {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        full_name: fullName,
                        phone: phone || null,
                    }),
                },
            );

            currentUser = updatedUser;

            sessionStorage.setItem(
                STORAGE_KEYS.user,
                JSON.stringify(updatedUser),
            );

            renderProfile(updatedUser);

            elements.success.textContent =
                "Đã cập nhật hồ sơ thành công.";
            elements.success.hidden = false;

            window.dispatchEvent(
                new CustomEvent("portal:profile-updated", {
                    detail: {
                        user: updatedUser,
                    },
                }),
            );
        } catch (error) {
            showError(error.message);
        } finally {
            setBusy(false);
        }
    }

    function resetMessages() {
        elements.error.textContent = "";
        elements.error.hidden = true;
        elements.success.textContent = "";
        elements.success.hidden = true;
    }

    function showError(message) {
        elements.success.hidden = true;
        elements.error.textContent = message;
        elements.error.hidden = false;
    }

    function setBusy(busy) {
        elements.submit.disabled = busy;
        elements.cancel.disabled = busy;
        elements.fullName.disabled = busy;
        elements.phone.disabled = busy;
        elements.submit.textContent = busy
            ? "Đang lưu..."
            : "Lưu hồ sơ";
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
