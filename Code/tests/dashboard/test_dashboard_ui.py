import re


async def test_dashboard_page_is_available_without_polluting_openapi(client):
    response = await client.get("/dashboard")
    assert response.status_code == 200
    assert "KPI Dashboard" in response.text

    schema = (await client.get("/openapi.json")).json()
    assert "/dashboard" not in schema["paths"]


async def test_dashboard_loads_dedicated_local_assets(client):
    html = (await client.get("/dashboard")).text
    assert 'href="/static/dashboard.css"' in html
    assert 'src="/static/dashboard.js"' in html
    assert "https://" not in html

    assert (await client.get("/static/dashboard.css")).status_code == 200
    assert (await client.get("/static/dashboard.js")).status_code == 200


async def test_dashboard_exposes_all_cv044_filters_with_labels(client):
    html = (await client.get("/dashboard")).text
    for field_id, label in (
        ("filter-from", "Từ ngày"),
        ("filter-to", "Đến ngày"),
        ("filter-category", "Danh mục"),
        ("filter-priority", "Ưu tiên"),
        ("filter-assignee", "Người xử lý"),
    ):
        assert f'for="{field_id}"' in html
        assert f'id="{field_id}"' in html
        assert label in html


async def test_dashboard_exposes_required_kpi_placeholders(client):
    html = (await client.get("/dashboard")).text
    for element_id in (
        "kpi-open",
        "kpi-reopened",
        "kpi-response",
        "kpi-sla",
        "kpi-satisfaction",
        "kpi-total",
    ):
        assert f'id="{element_id}"' in html


async def test_dashboard_has_accessible_loading_error_and_empty_states(client):
    html = (await client.get("/dashboard")).text
    assert 'id="dashboard-alert"' in html and 'role="alert"' in html
    assert 'id="loading-state"' in html and 'role="status"' in html
    assert 'id="dashboard-announcer"' in html and 'aria-live="polite"' in html
    assert 'id="empty-state"' in html
    assert 'class="skip-link"' in html


async def test_dashboard_has_explicit_success_failure_empty_and_denied_states(client):
    html = (await client.get("/dashboard")).text
    assert 'id="dashboard-success"' in html and 'role="status"' in html
    assert 'id="dashboard-alert"' in html and 'role="alert"' in html
    assert 'id="empty-state"' in html
    assert 'id="access-denied-state"' in html and 'role="alert"' in html
    assert 'id="denied-back-to-login"' in html

    script = (await client.get("/static/dashboard.js")).text
    assert "showDashboardSuccess" in script
    assert "showAccessDenied" in script
    assert 'response.status === 403' in script
    assert "Không thể kết nối đến máy chủ" in script


async def test_dashboard_script_integrates_cv043_and_filter_sources(client):
    script = (await client.get("/static/dashboard.js")).text
    for endpoint in (
        "/dashboard/overview",
        "/dashboard/sla-performance",
        "/categories",
        "/priorities",
        "/admin/users?role_code=PROCESSOR",
    ):
        assert endpoint in script
    for parameter in ("category_id", "priority_id", "assignee_id"):
        assert f'query.set("{parameter}"' in script


async def test_dashboard_uses_session_scoped_tokens_and_refresh(client):
    script = (await client.get("/static/dashboard.js")).text
    assert "sessionStorage" in script
    assert "localStorage" not in script
    assert 'headers.set("Authorization", `Bearer ${state.accessToken}`)' in script
    assert "/auth/refresh" in script
    assert "response.status === 401" in script
    assert "state.refreshPromise" in script


async def test_dashboard_does_not_embed_credentials_or_render_api_html(client):
    html = (await client.get("/dashboard")).text
    script = (await client.get("/static/dashboard.js")).text
    assert "innerHTML" not in script
    assert "requester@example.com" not in html + script
    assert "CorrectPassword" not in html + script
    assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}\.", html + script)


async def test_dashboard_handles_missing_samples_without_fake_zero(client):
    script = (await client.get("/static/dashboard.js")).text
    assert 'value == null ? "—"' in script
    assert 'return value == null ? "—"' in script
    assert '"Chưa có mẫu dữ liệu"' in script


async def test_dashboard_styles_target_supported_responsive_widths(client):
    css = (await client.get("/static/dashboard.css")).text
    for width in ("1180px", "900px", "768px", "390px"):
        assert f"@media (max-width: {width})" in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css


async def test_home_page_links_to_dashboard_and_keeps_sla_legend(client):
    html = (await client.get("/")).text
    assert 'href="/dashboard"' in html
    for code in ("ON_TRACK", "NEAR_DUE", "OVERDUE", "MET"):
        assert f'data-sla-status="{code}"' in html
