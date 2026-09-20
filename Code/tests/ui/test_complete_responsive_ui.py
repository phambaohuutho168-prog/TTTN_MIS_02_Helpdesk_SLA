import re

import pytest


pytestmark = pytest.mark.ui_complete


async def _assets(client):
    html = (await client.get("/dashboard")).text
    script = (await client.get("/static/dashboard.js")).text
    css = (await client.get("/static/dashboard.css")).text
    return html, script, css


async def test_cv056_exposes_all_required_ui_states(client):
    html, _script, _css = await _assets(client)
    for state in ("denied", "loading", "success", "failure", "empty"):
        assert f'data-ui-state="{state}"' in html
    for element_id in (
        "access-denied-state",
        "loading-state",
        "dashboard-success",
        "dashboard-alert",
        "empty-state",
        "retry-dashboard",
        "empty-reset-filters",
    ):
        assert f'id="{element_id}"' in html
    assert 'role="status"' in html
    assert 'role="alert"' in html
    assert 'aria-live="polite"' in html


async def test_cv056_displays_all_ticket_statuses_consistently(client):
    html, script, _css = await _assets(client)
    expected = {
        "NEW",
        "ASSIGNED",
        "IN_PROGRESS",
        "PENDING_INFO",
        "RESOLVED",
        "CLOSED",
        "REOPENED",
        "REJECTED",
    }
    assert set(re.findall(r'data-ticket-status="([A-Z_]+)"', html)) == expected
    for status in expected:
        assert f"{status}:" in script
    assert "WAITING_REQUESTER" not in script


async def test_cv056_supports_retry_reset_success_and_mobile_recovery(client):
    _html, script, _css = await _assets(client)
    for behavior in (
        'elements.retryDashboard.addEventListener("click", loadDashboard)',
        'elements.emptyResetFilters.addEventListener("click", resetFilters)',
        'elements.dismissSuccess.addEventListener("click"',
        "closeMobileNavigation",
        'event.key === "Escape"',
        'classList.toggle("is-loading", busy)',
    ):
        assert behavior in script
    assert "Không thể kết nối đến máy chủ" in script
    assert "Dữ liệu dashboard đã được cập nhật thành công." in script


async def test_cv056_responsive_css_covers_desktop_tablet_mobile_and_preferences(client):
    _html, _script, css = await _assets(client)
    for width in ("1180px", "900px", "768px", "560px", "390px"):
        assert f"@media (max-width: {width})" in css
    assert "grid-template-columns: repeat(6" in css
    assert "grid-template-columns: repeat(3" in css
    assert "grid-template-columns: repeat(2" in css
    assert "grid-template-columns: 1fr" in css
    assert "prefers-reduced-motion: reduce" in css
    assert "prefers-contrast: more" in css
    assert "@keyframes skeleton" in css


async def test_cv056_keeps_ui_safe_and_keyboard_accessible(client):
    html, script, css = await _assets(client)
    assert 'class="skip-link"' in html
    assert 'tabindex="-1" data-ui-state="failure"' in html
    assert 'aria-controls="mobile-nav"' in html
    assert ":focus-visible" in css
    assert "innerHTML" not in script
    assert "localStorage" not in script
    assert "CorrectPassword" not in html + script
