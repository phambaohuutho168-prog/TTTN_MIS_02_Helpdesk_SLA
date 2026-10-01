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