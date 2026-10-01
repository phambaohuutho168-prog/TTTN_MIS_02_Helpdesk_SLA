"use strict";

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

const state = {
    accessToken: sessionStorage.getItem(STORAGE_KEYS.accessToken),
    refreshToken: sessionStorage.getItem(STORAGE_KEYS.refreshToken),
    user: readStoredUser(),
};

const elements = {};

document.addEventListener("DOMContentLoaded", initialize);

function initialize() {
    cacheElements();

    elements.loginForm.addEventListener("submit", handleLogin);
    elements.logoutButton.addEventListener("click", handleLogout);

    if (state.accessToken && state.user) {
    showPortal();
} else {
    showLogin();
}
}

function cacheElements() {
    const ids = [
        "auth-panel",
        "login-form",
        "login-email",
        "login-password",
        "login-button",
        "login-error",
        "session-navigation",
        "current-user-name",
        "current-user-role",
        "logout-button",
        "portal-shell",
        "portal-title",
        "portal-description",
        "portal-message",
        "role-badge",
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
        clearStoredSession();
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

function clearStoredSession() {
    for (const key of Object.values(STORAGE_KEYS)) {
        sessionStorage.removeItem(key);
    }
}

function clearSession() {
    state.accessToken = null;
    state.refreshToken = null;
    state.user = null;
    clearStoredSession();
}

function roleCodes() {
    return new Set(
        (state.user?.roles || []).map((role) => role.role_code),
    );
}

function primaryRole() {
    const roles = roleCodes();

    if (roles.has("ADMIN")) return "ADMIN";
    if (roles.has("PROCESSOR")) return "PROCESSOR";
    if (roles.has("REQUESTER")) return "REQUESTER";

    return null;
}

async function handleLogin(event) {
    event.preventDefault();
    setLoginError("");
    setLoginBusy(true);

    try {
        const response = await fetch(`${API_PREFIX}/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body: JSON.stringify({
                email: elements.loginEmail.value.trim(),
                password: elements.loginPassword.value,
            }),
        });

        const payload = await parseResponse(response);

        if (!response.ok) {
            throw new Error(
                errorMessage(payload, "Đăng nhập không thành công."),
            );
        }

        storeSession(payload.data);
        elements.loginPassword.value = "";

        if (!primaryRole()) {
            clearSession();
            throw new Error("Tài khoản chưa có vai trò sử dụng hệ thống.");
        }

        showPortal();
    } catch (error) {
        setLoginError(
            error instanceof TypeError
                ? "Không thể kết nối đến máy chủ."
                : error.message,
        );
    } finally {
        setLoginBusy(false);
    }
}

function showLogin(message = "") {
    elements.authPanel.hidden = false;
    elements.portalShell.hidden = true;
    elements.sessionNavigation.hidden = true;
    setLoginError(message);

    window.setTimeout(() => elements.loginEmail.focus(), 0);
}

function showPortal() {
    const role = primaryRole();
    const roleLabel = ROLE_LABELS[role] || "Người dùng";

    elements.authPanel.hidden = true;
    elements.portalShell.hidden = false;
    elements.sessionNavigation.hidden = false;

    elements.currentUserName.textContent = state.user.full_name;
    elements.currentUserRole.textContent = roleLabel;
    elements.roleBadge.textContent = roleLabel;

    if (role === "ADMIN") {
        elements.portalTitle.textContent = "Điều phối và quản trị ticket";
        elements.portalDescription.textContent =
            "Theo dõi toàn hệ thống, phân công và kiểm soát SLA.";
    } else if (role === "PROCESSOR") {
        elements.portalTitle.textContent = "Hàng đợi xử lý";
        elements.portalDescription.textContent =
            "Theo dõi và xử lý những ticket được phân công.";
    } else {
        elements.portalTitle.textContent = "Yêu cầu hỗ trợ của tôi";
        elements.portalDescription.textContent =
            "Tạo mới và theo dõi những ticket bạn đã gửi.";
    }

    window.setTimeout(
        () => window.dispatchEvent(new Event("portal:authenticated")),
        0,
    );
}

async function handleLogout() {
    const accessToken = state.accessToken;
    const refreshToken = state.refreshToken;

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
        clearSession();
        elements.loginForm.reset();
        showLogin("Bạn đã đăng xuất khỏi hệ thống.");
    }
}

function setLoginBusy(busy) {
    elements.loginButton.disabled = busy;
    elements.loginEmail.disabled = busy;
    elements.loginPassword.disabled = busy;
    elements.loginButton.textContent = busy
        ? "Đang đăng nhập..."
        : "Đăng nhập";
}

function setLoginError(message) {
    elements.loginError.textContent = message;
    elements.loginError.hidden = !message;
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