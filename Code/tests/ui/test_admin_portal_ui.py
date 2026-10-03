import re


async def test_portal_and_admin_pages_are_available_without_polluting_openapi(
    client,
):
    portal_response = await client.get("/portal")
    admin_response = await client.get("/admin")

    assert portal_response.status_code == 200
    assert admin_response.status_code == 200
    assert 'id="portal-shell"' in portal_response.text
    assert 'id="user-create-panel"' in admin_response.text

    schema = (await client.get("/openapi.json")).json()
    assert "/portal" not in schema["paths"]
    assert "/admin" not in schema["paths"]


async def test_portal_and_admin_load_dedicated_local_assets(client):
    portal_html = (await client.get("/portal")).text
    admin_html = (await client.get("/admin")).text

    for asset in (
        "/static/portal.css",
        "/static/portal.js",
        "/static/portal-tickets.js",
    ):
        assert asset in portal_html
        assert (await client.get(asset)).status_code == 200

    for asset in (
        "/static/admin.css",
        "/static/admin.js",
    ):
        assert asset in admin_html
        assert (await client.get(asset)).status_code == 200


async def test_admin_page_exposes_user_management_controls(client):
    html = (await client.get("/admin")).text

    for element_id in (
        "user-create-panel",
        "user-create-form",
        "user-create-roles",
        "user-edit-dialog",
        "user-edit-form",
        "user-edit-roles",
    ):
        assert f'id="{element_id}"' in html

    assert 'id="user-create-is-active"' in html
    assert 'id="user-edit-is-active"' in html
    assert 'type="dialog"' not in html
    assert "<dialog" in html


async def test_admin_script_integrates_user_management_endpoints(client):
    script = (await client.get("/static/admin.js")).text

    for endpoint in (
        "/admin/users",
        "/admin/roles",
        "/admin/departments",
    ):
        assert endpoint in script

    for method in ("POST", "PATCH", "PUT", "DELETE"):
        assert f'method: "{method}"' in script


async def test_admin_uses_session_tokens_and_safe_dom_rendering(client):
    html = (await client.get("/admin")).text
    script = (await client.get("/static/admin.js")).text

    assert "sessionStorage" in script
    assert "localStorage" not in script
    assert "/auth/refresh" in script
    assert "response.status === 401" in script
    assert "innerHTML" not in script
    assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}\.", html + script)


async def test_portal_shows_admin_navigation_only_for_admin_role(client):
    html = (await client.get("/portal")).text
    script = (await client.get("/static/portal.js")).text

    assert 'id="admin-navigation-link"' in html
    assert 'href="/admin"' in html
    assert "adminNavigationLink.hidden" in script
    assert 'role !== "ADMIN"' in script


async def test_admin_styles_support_mobile_and_table_overflow(client):
    css = (await client.get("/static/admin.css")).text

    assert "@media (max-width: 640px)" in css
    assert "overflow-x: auto" in css
    assert ".admin-edit-card" in css
    assert ".admin-create-panel" in css

async def test_portal_exposes_notification_center_and_local_asset(client):
    html = (await client.get("/portal")).text

    assert "/static/portal-notifications.js" in html

    for element_id in (
        "notification-center",
        "notification-toggle",
        "notification-unread-count",
        "notification-panel",
        "notification-filter",
        "notification-mark-all",
        "notification-list",
        "notification-previous",
        "notification-next",
    ):
        assert f'id="{element_id}"' in html

    assert (
        await client.get("/static/portal-notifications.js")
    ).status_code == 200


async def test_notification_script_integrates_api_and_ticket_detail(client):
    notification_script = (
        await client.get("/static/portal-notifications.js")
    ).text
    ticket_script = (
        await client.get("/static/portal-tickets.js")
    ).text

    for endpoint in (
        "/notifications?is_read=false",
        "/notifications/read-all",
        "/notifications/${notification.notification_id}/read",
    ):
        assert endpoint in notification_script

    assert "portal:open-ticket" in notification_script
    assert "portal:open-ticket" in ticket_script
    assert "openTicketDetail(ticketId)" in ticket_script


async def test_notification_ui_uses_safe_rendering_and_mobile_styles(client):
    script = (
        await client.get("/static/portal-notifications.js")
    ).text
    css = (await client.get("/static/portal.css")).text

    assert "sessionStorage" in script
    assert "localStorage" not in script
    assert "innerHTML" not in script
    assert "NOTIFICATION_TYPE_LABELS" in script
    assert ".notification-panel" in css
    assert ".notification-item--unread" in css
    assert "@media (max-width: 640px)" in css
async def test_portal_exposes_profile_dialog_and_local_asset(client):
    html = (await client.get("/portal")).text

    assert "/static/portal-profile.js" in html

    for element_id in (
        "profile-open",
        "profile-dialog",
        "profile-close",
        "profile-form",
        "profile-email",
        "profile-full-name",
        "profile-phone",
        "profile-department",
        "profile-role-list",
        "profile-submit",
        "profile-cancel",
    ):
        assert f'id="{element_id}"' in html

    assert (
        await client.get("/static/portal-profile.js")
    ).status_code == 200


async def test_profile_script_updates_current_user_safely(client):
    profile_script = (
        await client.get("/static/portal-profile.js")
    ).text
    portal_script = (
        await client.get("/static/portal.js")
    ).text

    assert '"/users/me"' in profile_script
    assert 'method: "PATCH"' in profile_script
    assert "sessionStorage" in profile_script
    assert "localStorage" not in profile_script
    assert "innerHTML" not in profile_script
    assert "portal:profile-updated" in profile_script
    assert "portal:profile-updated" in portal_script
    assert "handleProfileUpdated" in portal_script


async def test_profile_styles_support_desktop_and_mobile(client):
    css = (await client.get("/static/portal.css")).text

    assert ".profile-card" in css
    assert ".profile-grid" in css
    assert ".profile-role-badge" in css
    assert "width: calc(100vw - 20px)" in css
    assert "grid-template-columns: 1fr" in css
async def test_admin_exposes_ticket_catalog_management(client):
    html = (await client.get("/admin")).text

    assert "/static/admin-catalogs.js" in html

    for element_id in (
        "category-management-section",
        "category-form",
        "category-name",
        "category-description",
        "category-is-active",
        "category-table-body",
        "priority-management-section",
        "priority-form",
        "priority-code",
        "priority-level",
        "priority-name",
        "priority-description",
        "priority-is-active",
        "priority-table-body",
    ):
        assert f'id="{element_id}"' in html

    assert (
        await client.get("/static/admin-catalogs.js")
    ).status_code == 200


async def test_admin_catalog_script_integrates_catalog_endpoints(client):
    script = (
        await client.get("/static/admin-catalogs.js")
    ).text

    for endpoint in (
        "/categories?is_active=true",
        "/categories?is_active=false",
        "/priorities?is_active=true",
        "/priorities?is_active=false",
        "/admin/categories",
        "/admin/priorities",
    ):
        assert endpoint in script

    assert 'editingId ? "PATCH" : "POST"' in script
    assert "admin:authenticated" in script
    assert "loadCategories()" in script
    assert "loadPriorities()" in script


async def test_admin_catalog_ui_uses_safe_rendering_and_responsive_styles(
    client,
):
    script = (
        await client.get("/static/admin-catalogs.js")
    ).text
    css = (await client.get("/static/admin.css")).text

    assert "sessionStorage" in script
    assert "localStorage" not in script
    assert "innerHTML" not in script
    assert "document.createElement" in script
    assert "replaceChildren" in script
    assert "/auth/refresh" in script

    for selector in (
        ".admin-catalog-section",
        ".admin-catalog-form",
        ".catalog-status--active",
        ".catalog-status--inactive",
        ".priority-code",
    ):
        assert selector in css

    assert "@media (max-width: 768px)" in css
    assert "@media (max-width: 480px)" in css
async def test_admin_exposes_audit_log_interface(client):
    html = (await client.get("/admin")).text

    assert "/static/admin-audit.js" in html

    for element_id in (
        "audit-log-section",
        "audit-filter-form",
        "audit-filter-actor",
        "audit-filter-ticket",
        "audit-filter-action",
        "audit-filter-entity-type",
        "audit-filter-from",
        "audit-filter-to",
        "audit-page-size",
        "audit-table-body",
        "audit-pagination",
        "audit-detail-dialog",
        "audit-detail-old-value",
        "audit-detail-new-value",
    ):
        assert f'id="{element_id}"' in html

    assert 'type="datetime-local"' in html
    assert (
        await client.get("/static/admin-audit.js")
    ).status_code == 200


async def test_admin_audit_script_integrates_filters_and_pagination(
    client,
):
    script = (
        await client.get("/static/admin-audit.js")
    ).text

    assert "/admin/audit-logs?" in script

    for parameter in (
        "actor_user_id",
        "ticket_id",
        "action_code",
        "entity_type",
        "created_from",
        "created_to",
        "page_size",
    ):
        assert parameter in script

    assert 'query.set("page"' in script
    assert 'query.set("page_size"' in script
    assert "showPreviousPage" in script
    assert "showNextPage" in script
    assert "openAuditDetail" in script
    assert "ACTION_LABELS" in script


async def test_admin_audit_uses_safe_rendering_and_responsive_styles(
    client,
):
    script = (
        await client.get("/static/admin-audit.js")
    ).text
    css = (await client.get("/static/admin.css")).text

    assert "sessionStorage" in script
    assert "localStorage" not in script
    assert "innerHTML" not in script
    assert "document.createElement" in script
    assert "replaceChildren" in script
    assert "JSON.stringify(value, null, 2)" in script
    assert "/auth/refresh" in script

    for selector in (
        ".admin-audit-section",
        ".admin-audit-filter",
        ".audit-detail-card",
        ".audit-detail-meta",
        ".audit-change-grid",
        "#audit-detail-dialog",
    ):
        assert selector in css

    assert "@media (max-width: 960px)" in css
    assert "@media (max-width: 640px)" in css
    assert "overflow-x: hidden" in css
async def test_portal_exposes_ticket_history_timeline(client):
    html = (await client.get("/portal")).text

    for element_id in (
        "ticket-history-section",
        "ticket-history-title",
        "ticket-history-reload",
        "ticket-history-summary",
        "ticket-history-loading",
        "ticket-history-error",
        "ticket-history-empty",
        "ticket-history-timeline",
    ):
        assert f'id="{element_id}"' in html

    assert 'aria-label="Dòng thời gian xử lý ticket"' in html


async def test_ticket_script_integrates_status_and_assignment_history(
    client,
):
    script = (
        await client.get("/static/portal-tickets.js")
    ).text

    assert "/status-history" in script
    assert "/assignments" in script
    assert "loadTicketHistory(ticket)" in script
    assert "fetchAllHistoryPages" in script
    assert "statusHistoryEvent" in script
    assert "assignmentHistoryEvent" in script
    assert "PENDING_INFO" in script
    assert "innerHTML" not in script


async def test_ticket_history_styles_support_timeline_and_mobile(
    client,
):
    css = (await client.get("/static/portal.css")).text

    for selector in (
        ".ticket-history-timeline",
        ".ticket-history-item",
        ".ticket-history-marker",
        ".ticket-history-card",
        ".ticket-history-item--assignment",
        ".ticket-history-kind--status",
        ".ticket-history-kind--assignment",
    ):
        assert selector in css

    assert "@media (max-width: 640px)" in css
async def test_portal_exposes_ticket_sla_detail_controls(client):
    html = (await client.get("/portal")).text

    for element_id in (
        "ticket-sla-section",
        "ticket-sla-overall",
        "ticket-sla-reload",
        "ticket-sla-loading",
        "ticket-sla-error",
        "ticket-sla-content",
        "ticket-sla-first-response",
        "ticket-sla-response-empty",
        "ticket-sla-response-container",
        "ticket-sla-resolution-empty",
        "ticket-sla-resolution-list",
    ):
        assert f'id="{element_id}"' in html

    assert 'id="ticket-detail-response-deadline"' in html
    assert 'id="ticket-detail-resolution-deadline"' in html
    assert 'id="ticket-detail-description"' in html


async def test_ticket_sla_script_integrates_detail_endpoint_safely(client):
    script = (
        await client.get("/static/portal-tickets.js")
    ).text

    assert "`/tickets/${ticketId}/sla`" in script
    assert "loadTicketSla(ticket)" in script
    assert "handleTicketSlaReload" in script
    assert "renderTicketSla" in script
    assert "createTicketSlaCard" in script
    assert "setTicketSlaStatusBadge" in script
    assert "replaceChildren" in script
    assert "innerHTML" not in script


async def test_ticket_sla_styles_support_status_progress_and_mobile(client):
    css = (await client.get("/static/portal.css")).text

    for selector in (
        ".ticket-sla-card",
        ".ticket-sla-card__grid",
        ".ticket-sla-progress",
        ".sla-status-badge--warning",
        ".sla-status-badge--danger",
        ".sla-status-badge--success",
    ):
        assert selector in css

    assert "@media (max-width: 640px)" in css
async def test_portal_exposes_sla_monitor_and_local_asset(client):
    html = (await client.get("/portal")).text

    assert "/static/portal-sla.js" in html

    for element_id in (
        "sla-monitor-section",
        "sla-monitor-total",
        "sla-monitor-reload",
        "sla-monitor-filter-form",
        "sla-monitor-filter-state",
        "sla-monitor-filter-type",
        "sla-monitor-filter-ticket",
        "sla-monitor-filter-from",
        "sla-monitor-filter-to",
        "sla-monitor-page-size",
        "sla-monitor-table-body",
        "sla-monitor-pagination",
        "sla-monitor-page-previous",
        "sla-monitor-page-next",
    ):
        assert f'id="{element_id}"' in html

    assert (
        await client.get("/static/portal-sla.js")
    ).status_code == 200


async def test_sla_monitor_script_integrates_filters_and_ticket_detail(client):
    script = (await client.get("/static/portal-sla.js")).text

    assert "/sla/breaches?" in script
    assert 'query.append("state"' in script
    assert 'query.set("sla_type"' in script
    assert '"ticket_id"' in script
    assert '"triggered_from"' in script
    assert '"triggered_to"' in script
    assert "portal:open-ticket" in script
    assert '["ADMIN", "PROCESSOR"].includes(role)' in script
    assert "elements.section.hidden = true" in script
    assert "sessionStorage" in script
    assert "localStorage" not in script
    assert "innerHTML" not in script


async def test_sla_monitor_styles_support_states_table_and_mobile(client):
    css = (await client.get("/static/portal.css")).text

    for selector in (
        ".sla-monitor-section",
        ".sla-monitor-filter-grid",
        ".sla-event-badge--warning",
        ".sla-event-badge--overdue",
        ".sla-event-badge--escalated",
        ".sla-monitor-row--overdue",
        ".sla-monitor-row--escalated",
    ):
        assert selector in css

    assert "#sla-monitor-table-wrapper" in css
    assert "overflow-x: auto" in css
    assert "@media (max-width: 640px)" in css
