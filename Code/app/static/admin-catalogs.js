"use strict";

(() => {
    const API_PREFIX = "/api/v1";

    const STORAGE_KEYS = Object.freeze({
        accessToken: "helpdesk.dashboard.accessToken",
        refreshToken: "helpdesk.dashboard.refreshToken",
        user: "helpdesk.dashboard.user",
    });

   const catalogState = {
    started: false,
    categories: [],
    editingCategoryId: null,
    priorities: [],
    editingPriorityId: null,
};

    const elements = {};

    window.addEventListener(
        "admin:authenticated",
        startCatalogWorkspace,
    );

    function startCatalogWorkspace() {
        if (catalogState.started) return;

        catalogState.started = true;
        cacheElements();

        elements.form.addEventListener("submit", handleCategorySubmit);
        elements.cancelEdit.addEventListener("click", resetCategoryForm);
        elements.priorityForm.addEventListener("submit",handlePrioritySubmit,);
        elements.priorityCancelEdit.addEventListener("click",resetPriorityForm,);
        elements.priorityCode.addEventListener("change",syncPriorityLevel,);

        Promise.all([
            loadCategories(),
            loadPriorities(),
        ]);
    }

    function cacheElements() {
        elements.total = document.getElementById("category-total");
        elements.message = document.getElementById("category-message");
        elements.form = document.getElementById("category-form");
        elements.formError = document.getElementById("category-form-error",);
        elements.editId = document.getElementById("category-edit-id");
        elements.name = document.getElementById("category-name");
        elements.description = document.getElementById("category-description",);
        elements.isActive = document.getElementById("category-is-active",);
        elements.submit = document.getElementById("category-submit");
        elements.cancelEdit = document.getElementById("category-cancel-edit",);
        elements.loading = document.getElementById("category-list-loading",);
        elements.listError = document.getElementById("category-list-error",);
        elements.empty = document.getElementById("category-list-empty",);
        elements.tableWrapper = document.getElementById("category-table-wrapper",);
        elements.tableBody = document.getElementById("category-table-body",);
        elements.priorityTotal = document.getElementById("priority-total");
        elements.priorityMessage = document.getElementById("priority-message");
        elements.priorityForm = document.getElementById("priority-form");
        elements.priorityFormError = document.getElementById("priority-form-error");
        elements.priorityEditId = document.getElementById("priority-edit-id");
        elements.priorityCode = document.getElementById("priority-code");
        elements.priorityLevel = document.getElementById("priority-level");
        elements.priorityName = document.getElementById("priority-name");
        elements.priorityDescription = document.getElementById("priority-description");
        elements.priorityIsActive = document.getElementById("priority-is-active");
        elements.prioritySubmit = document.getElementById("priority-submit");
        elements.priorityCancelEdit = document.getElementById("priority-cancel-edit");
        elements.priorityLoading = document.getElementById("priority-list-loading");
        elements.priorityListError = document.getElementById("priority-list-error");
        elements.priorityEmpty = document.getElementById("priority-list-empty");
        elements.priorityTableWrapper = document.getElementById("priority-table-wrapper");
        elements.priorityTableBody = document.getElementById("priority-table-body");
    }

    async function loadCategories() {
        elements.loading.hidden = false;
        elements.listError.hidden = true;
        elements.empty.hidden = true;
        elements.tableWrapper.hidden = true;

        try {
            const [activeCategories, inactiveCategories] =
                await Promise.all([
                    apiRequest("/categories?is_active=true"),
                    apiRequest("/categories?is_active=false"),
                ]);

            const categoriesById = new Map();

            for (const category of [
                ...(activeCategories || []),
                ...(inactiveCategories || []),
            ]) {
                categoriesById.set(category.category_id, category);
            }

            catalogState.categories = Array.from(
                categoriesById.values(),
            ).sort((first, second) =>
                first.category_name.localeCompare(
                    second.category_name,
                    "vi",
                ),
            );

            renderCategories();
        } catch (error) {
            elements.listError.textContent = error.message;
            elements.listError.hidden = false;
        } finally {
            elements.loading.hidden = true;
        }
    }

    function renderCategories() {
        elements.tableBody.replaceChildren();

        const total = catalogState.categories.length;
        elements.total.textContent = `${total} danh mục`;

        if (total === 0) {
            elements.empty.hidden = false;
            elements.tableWrapper.hidden = true;
            return;
        }

        const fragment = document.createDocumentFragment();

        for (const category of catalogState.categories) {
            fragment.append(createCategoryRow(category));
        }

        elements.tableBody.append(fragment);
        elements.empty.hidden = true;
        elements.tableWrapper.hidden = false;
    }

    function createCategoryRow(category) {
        const row = document.createElement("tr");

        const nameCell = document.createElement("td");
        const name = document.createElement("strong");
        name.textContent = category.category_name;
        nameCell.append(name);

        const descriptionCell = document.createElement("td");
        descriptionCell.className = "catalog-description";
        descriptionCell.textContent =
            category.description || "Không có mô tả";

        const statusCell = document.createElement("td");
        const status = document.createElement("span");
        status.className = category.is_active
            ? "catalog-status catalog-status--active"
            : "catalog-status catalog-status--inactive";
        status.textContent = category.is_active
            ? "Đang sử dụng"
            : "Ngừng sử dụng";
        statusCell.append(status);

        const actionCell = document.createElement("td");
        const editButton = document.createElement("button");
        editButton.type = "button";
        editButton.className =
            "button button--secondary catalog-edit-button";
        editButton.textContent = "Chỉnh sửa";
        editButton.addEventListener("click", () => {
            beginCategoryEdit(category);
        });
        actionCell.append(editButton);

        row.append(
            nameCell,
            descriptionCell,
            statusCell,
            actionCell,
        );

        return row;
    }

    function beginCategoryEdit(category) {
        catalogState.editingCategoryId = category.category_id;

        elements.editId.value = String(category.category_id);
        elements.name.value = category.category_name;
        elements.description.value = category.description || "";
        elements.isActive.checked = category.is_active;

        elements.submit.textContent = "Lưu thay đổi";
        elements.cancelEdit.hidden = false;
        hideCategoryFormError();

        elements.form.scrollIntoView({
            behavior: "smooth",
            block: "center",
        });

        window.setTimeout(() => elements.name.focus(), 250);
    }

    function resetCategoryForm() {
        catalogState.editingCategoryId = null;

        elements.form.reset();
        elements.editId.value = "";
        elements.isActive.checked = true;
        elements.submit.textContent = "Tạo danh mục";
        elements.cancelEdit.hidden = true;

        hideCategoryFormError();
    }

    async function handleCategorySubmit(event) {
        event.preventDefault();
        hideCategoryFormError();
        hideCategoryMessage();

        const categoryName = elements.name.value.trim();

        if (!categoryName) {
            showCategoryFormError("Vui lòng nhập tên danh mục.");
            elements.name.focus();
            return;
        }

        const payload = {
            category_name: categoryName,
            description:
                elements.description.value.trim() || null,
            is_active: elements.isActive.checked,
        };

        const editingId = catalogState.editingCategoryId;
        const path = editingId
            ? `/admin/categories/${editingId}`
            : "/admin/categories";
        const method = editingId ? "PATCH" : "POST";

        setCategoryFormBusy(true);

        try {
            await apiRequest(path, {
                method,
                body: JSON.stringify(payload),
            });

            showCategoryMessage(
                editingId
                    ? "Đã cập nhật danh mục thành công."
                    : "Đã tạo danh mục thành công.",
            );

            resetCategoryForm();
            await loadCategories();
        } catch (error) {
            showCategoryFormError(error.message);
        } finally {
            setCategoryFormBusy(false);
        }
    }

    function setCategoryFormBusy(busy) {
        elements.name.disabled = busy;
        elements.description.disabled = busy;
        elements.isActive.disabled = busy;
        elements.submit.disabled = busy;
        elements.cancelEdit.disabled = busy;

        if (busy) {
            elements.submit.textContent =
                catalogState.editingCategoryId
                    ? "Đang lưu..."
                    : "Đang tạo...";
        } else {
            elements.submit.textContent =
                catalogState.editingCategoryId
                    ? "Lưu thay đổi"
                    : "Tạo danh mục";
        }
    }

    function showCategoryMessage(message) {
        elements.message.className = "alert alert--success";
        elements.message.textContent = message;
        elements.message.hidden = false;
    }

    function hideCategoryMessage() {
        elements.message.hidden = true;
        elements.message.textContent = "";
    }

    function showCategoryFormError(message) {
        elements.formError.textContent = message;
        elements.formError.hidden = false;
    }

    function hideCategoryFormError() {
        elements.formError.textContent = "";
        elements.formError.hidden = true;
    }

    async function loadPriorities() {
        elements.priorityLoading.hidden = false;
        elements.priorityListError.hidden = true;
        elements.priorityEmpty.hidden = true;
        elements.priorityTableWrapper.hidden = true;

        try {
            const [activePriorities, inactivePriorities] =
                await Promise.all([
                    apiRequest("/priorities?is_active=true"),
                    apiRequest("/priorities?is_active=false"),
                ]);

            const prioritiesById = new Map();

            for (const priority of [
                ...(activePriorities || []),
                ...(inactivePriorities || []),
            ]) {
                prioritiesById.set(priority.priority_id, priority);
            }

            catalogState.priorities = Array.from(
                prioritiesById.values(),
            ).sort(
                (first, second) =>
                    first.priority_level - second.priority_level,
            );

            renderPriorities();
            updatePriorityCodeAvailability();
        } catch (error) {
            elements.priorityListError.textContent = error.message;
            elements.priorityListError.hidden = false;
        } finally {
            elements.priorityLoading.hidden = true;
        }
    }

    function renderPriorities() {
        elements.priorityTableBody.replaceChildren();

        const total = catalogState.priorities.length;
        elements.priorityTotal.textContent =
            `${total} mức ưu tiên`;

        if (total === 0) {
            elements.priorityEmpty.hidden = false;
            elements.priorityTableWrapper.hidden = true;
            return;
        }

        const fragment = document.createDocumentFragment();

        for (const priority of catalogState.priorities) {
            fragment.append(createPriorityRow(priority));
        }

        elements.priorityTableBody.append(fragment);
        elements.priorityEmpty.hidden = true;
        elements.priorityTableWrapper.hidden = false;
    }

    function createPriorityRow(priority) {
        const row = document.createElement("tr");

        const codeCell = document.createElement("td");
        const code = document.createElement("span");
        code.className = "priority-code";
        code.textContent =
            `${priority.priority_code} · Cấp ${priority.priority_level}`;
        codeCell.append(code);

        const nameCell = document.createElement("td");
        const name = document.createElement("strong");
        name.textContent = priority.priority_name;
        nameCell.append(name);

        const descriptionCell = document.createElement("td");
        descriptionCell.className = "catalog-description";
        descriptionCell.textContent =
            priority.description || "Không có mô tả";

        const statusCell = document.createElement("td");
        const status = document.createElement("span");
        status.className = priority.is_active
            ? "catalog-status catalog-status--active"
            : "catalog-status catalog-status--inactive";
        status.textContent = priority.is_active
            ? "Đang sử dụng"
            : "Ngừng sử dụng";
        statusCell.append(status);

        const actionCell = document.createElement("td");
        const editButton = document.createElement("button");
        editButton.type = "button";
        editButton.className =
            "button button--secondary catalog-edit-button";
        editButton.textContent = "Chỉnh sửa";
        editButton.addEventListener("click", () => {
            beginPriorityEdit(priority);
        });
        actionCell.append(editButton);

        row.append(
            codeCell,
            nameCell,
            descriptionCell,
            statusCell,
            actionCell,
        );

        return row;
    }

    function syncPriorityLevel() {
        const code = elements.priorityCode.value;

        elements.priorityLevel.value = /^P[1-4]$/.test(code)
            ? code.slice(1)
            : "";
    }

    function beginPriorityEdit(priority) {
        catalogState.editingPriorityId = priority.priority_id;

        for (const option of elements.priorityCode.options) {
            option.disabled = false;
        }

        elements.priorityEditId.value =
            String(priority.priority_id);
        elements.priorityCode.value = priority.priority_code;
        elements.priorityLevel.value =
            String(priority.priority_level);
        elements.priorityName.value = priority.priority_name;
        elements.priorityDescription.value =
            priority.description || "";
        elements.priorityIsActive.checked = priority.is_active;

        elements.priorityCode.disabled = true;
        elements.priorityLevel.disabled = true;
        elements.prioritySubmit.disabled = false;
        elements.prioritySubmit.textContent = "Lưu thay đổi";
        elements.priorityCancelEdit.hidden = false;

        hidePriorityFormError();

        elements.priorityForm.scrollIntoView({
            behavior: "smooth",
            block: "center",
        });

        window.setTimeout(
            () => elements.priorityName.focus(),
            250,
        );
    }

    function resetPriorityForm() {
        catalogState.editingPriorityId = null;

        elements.priorityForm.reset();
        elements.priorityEditId.value = "";
        elements.priorityLevel.value = "";
        elements.priorityCode.disabled = false;
        elements.priorityLevel.disabled = false;
        elements.priorityLevel.readOnly = true;
        elements.priorityIsActive.checked = true;
        elements.prioritySubmit.textContent =
            "Tạo mức ưu tiên";
        elements.priorityCancelEdit.hidden = true;

        hidePriorityFormError();
        updatePriorityCodeAvailability();
    }

    function updatePriorityCodeAvailability() {
        if (catalogState.editingPriorityId) return;

        const usedCodes = new Set(
            catalogState.priorities.map(
                (priority) => priority.priority_code,
            ),
        );

        for (const option of elements.priorityCode.options) {
            if (!option.value) continue;

            option.disabled = usedCodes.has(option.value);
        }

        const allCodesUsed = ["P1", "P2", "P3", "P4"].every(
            (code) => usedCodes.has(code),
        );

        elements.prioritySubmit.disabled = allCodesUsed;
        elements.prioritySubmit.title = allCodesUsed
            ? "Hệ thống đã có đủ bốn mức ưu tiên P1–P4."
            : "";
    }

    async function handlePrioritySubmit(event) {
        event.preventDefault();
        hidePriorityFormError();
        hidePriorityMessage();

        const code = elements.priorityCode.value;
        const name = elements.priorityName.value.trim();
        const editingId = catalogState.editingPriorityId;

        if (!editingId && !/^P[1-4]$/.test(code)) {
            showPriorityFormError(
                "Vui lòng chọn mã ưu tiên từ P1 đến P4.",
            );
            elements.priorityCode.focus();
            return;
        }

        if (!name) {
            showPriorityFormError(
                "Vui lòng nhập tên mức ưu tiên.",
            );
            elements.priorityName.focus();
            return;
        }

        const commonPayload = {
            priority_name: name,
            description:
                elements.priorityDescription.value.trim() || null,
            is_active: elements.priorityIsActive.checked,
        };

        const payload = editingId
            ? commonPayload
            : {
                priority_code: code,
                priority_level: Number(code.slice(1)),
                ...commonPayload,
            };

        const path = editingId
            ? `/admin/priorities/${editingId}`
            : "/admin/priorities";
        const method = editingId ? "PATCH" : "POST";

        setPriorityFormBusy(true);

        try {
            await apiRequest(path, {
                method,
                body: JSON.stringify(payload),
            });

            showPriorityMessage(
                editingId
                    ? "Đã cập nhật mức ưu tiên thành công."
                    : "Đã tạo mức ưu tiên thành công.",
            );

            resetPriorityForm();
            await loadPriorities();
        } catch (error) {
            showPriorityFormError(error.message);
        } finally {
            setPriorityFormBusy(false);
        }
    }

    function setPriorityFormBusy(busy) {
        elements.priorityCode.disabled =
            busy || Boolean(catalogState.editingPriorityId);
        elements.priorityLevel.disabled = busy;
        elements.priorityName.disabled = busy;
        elements.priorityDescription.disabled = busy;
        elements.priorityIsActive.disabled = busy;
        elements.prioritySubmit.disabled = busy;
        elements.priorityCancelEdit.disabled = busy;

        if (busy) {
            elements.prioritySubmit.textContent =
                catalogState.editingPriorityId
                    ? "Đang lưu..."
                    : "Đang tạo...";
            return;
        }

        elements.prioritySubmit.textContent =
            catalogState.editingPriorityId
                ? "Lưu thay đổi"
                : "Tạo mức ưu tiên";

        if (!catalogState.editingPriorityId) {
            elements.priorityCode.disabled = false;
            updatePriorityCodeAvailability();
        }
    }

    function showPriorityMessage(message) {
        elements.priorityMessage.className =
            "alert alert--success";
        elements.priorityMessage.textContent = message;
        elements.priorityMessage.hidden = false;
    }

    function hidePriorityMessage() {
        elements.priorityMessage.textContent = "";
        elements.priorityMessage.hidden = true;
    }

    function showPriorityFormError(message) {
        elements.priorityFormError.textContent = message;
        elements.priorityFormError.hidden = false;
    }

    function hidePriorityFormError() {
        elements.priorityFormError.textContent = "";
        elements.priorityFormError.hidden = true;
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

        if (options.body && !(options.body instanceof FormData)) {
            headers.set("Content-Type", "application/json");
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
