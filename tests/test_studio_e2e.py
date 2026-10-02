#!/usr/bin/env python3
"""End-to-End browser tests for Taku Studio using Playwright and system Chrome.

Implements the workspace verification contract:
"写完从真实页面对答案。测遍了不会说谎的那一半，也要测遍会说谎的那一半.
用e2e和tdd方式生产级构建. Tested Till Good."
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

STUDIO_DIR = Path(__file__).resolve().parent.parent
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SCREENSHOTS_DIR = STUDIO_DIR / "screenshots"
STUDIO_PORT = 8765
STUDIO_URL = f"http://127.0.0.1:{STUDIO_PORT}"


def is_server_running(url: str = STUDIO_URL, timeout: float = 1.0) -> bool:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"{url}/api/health", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def studio_server():
    """Ensure the Taku Studio server is running, starting it if necessary."""
    proc = None
    if not is_server_running():
        server_py = str(STUDIO_DIR / "server.py")
        proc = subprocess.Popen(
            [sys.executable, server_py, "--port", str(STUDIO_PORT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait up to 5 seconds for server to come up
        start = time.time()
        while time.time() - start < 5.0:
            if is_server_running():
                break
            time.sleep(0.2)
        if not is_server_running():
            if proc:
                proc.terminate()
            raise RuntimeError(f"Failed to start Taku Studio server on port {STUDIO_PORT}")

    yield STUDIO_URL

    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="module")
def browser_context():
    """Launch system Chrome in headless mode with realistic dimensions."""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=CHROME_PATH,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        yield context
        browser.close()


def test_taku_studio_e2e_full_flow(studio_server, browser_context):
    page = browser_context.new_page()

    # 1. Navigate to Taku Studio
    page.goto(studio_server, wait_until="domcontentloaded", timeout=15000)
    assert "Taku Studio" in page.title()

    # 2. Verify Header & Connection Status
    connection_pill = page.locator("#connectionStatus")
    assert connection_pill.is_visible()
    assert "Live" in connection_pill.inner_text() or "Connected" in connection_pill.inner_text()

    # 3. Wait for Campaigns list to populate
    page.wait_for_selector(".campaign-card", timeout=25000)
    cards = page.locator(".campaign-card")
    assert cards.count() >= 1, "Expected at least 1 campaign card"

    # 4. Verify Center Stage Preview
    page.wait_for_selector("#popupMediaImage:visible, #bannerBar:visible", timeout=25000)
    headline = page.locator("#popupHeadline")
    if headline.is_visible():
        assert len(headline.inner_text().strip()) > 0

    # 5. Test Interactive Form Submission in Preview (if form is present)
    email_input = page.locator("#interactivePopupForm input[type='email']")
    if email_input.is_visible():
        email_input.fill("growth_engineer@example.com")
        submit_btn = page.locator("#popupSubmitBtn")
        if submit_btn.is_visible():
            submit_btn.click()
            success_banner = page.locator("#popupSuccessBanner")
            assert success_banner.is_visible()

    # 6. Capture Desktop Masterpiece Screenshot
    desktop_shot_path = str(SCREENSHOTS_DIR / "e2e_taku_studio_desktop.png")
    page.screenshot(path=desktop_shot_path, full_page=False)
    assert os.path.exists(desktop_shot_path)

    # 7. Test Multi-Space Switching if multiple spaces exist
    options = page.eval_on_selector_all("#spaceSelector option", "opts => opts.map(o => o.value).filter(Boolean)")
    if len(options) >= 2:
        page.select_option("#spaceSelector", options[-1])
        page.wait_for_selector(".campaign-card, #emptyCampaigns, .empty-state", timeout=10000)
        meta_text = page.locator("#currentSpaceMeta").inner_text()
        assert "Domain:" in meta_text or "Key:" in meta_text

        # Click first campaign in selected space if present
        second_cards = page.locator(".campaign-card")
        if second_cards.count() > 0:
            second_cards.first.click()
            time.sleep(0.5)

    modal_shot = str(SCREENSHOTS_DIR / "e2e_taku_studio_modal.png")
    page.screenshot(path=modal_shot, full_page=False)
    assert os.path.exists(modal_shot)

    # 8. Test Trigger Simulator
    sim_tab_btn = page.locator("button.tab-btn[data-tab='simulator']")
    sim_tab_btn.click()

    # Run matching URL simulation
    current_url_bar = page.locator("#frameUrlBar").inner_text()
    page.fill("#simTestUrl", current_url_bar if current_url_bar else "https://example.com/demo")
    page.click("#btnRunSimulation")
    page.wait_for_selector(".sim-result-card", timeout=5000)
    sim_card = page.locator(".sim-result-card")
    assert sim_card.is_visible()

    # Run non-matching URL simulation (Adversarial check: 测遍了会说谎的那一半)
    page.fill("#simTestUrl", "https://unrelated-domain.invalid/landing")
    page.click("#btnRunSimulation")
    time.sleep(0.3)
    assert "TRIGGER SUPPRESSED" in sim_card.inner_text() or "RULES_NOT_MATCHED" in sim_card.inner_text()

    # 9. Test Embed Snippet Tab
    snippet_tab_btn = page.locator("button.tab-btn[data-tab='snippet']")
    snippet_tab_btn.click()
    code_box = page.locator("#embedSnippetCode")
    assert code_box.is_visible()
    assert "cdn.taku.cool/js/latest.js" in code_box.inner_text()
    assert "api_public_key" in code_box.inner_text()

    # 10. Test Mobile Viewport Switching & Screenshot
    mobile_vp_btn = page.locator(".viewport-btn[data-viewport='mobile']")
    mobile_vp_btn.click()
    device_frame = page.locator("#deviceFrame")
    assert "mobile" in (device_frame.get_attribute("class") or "")

    mobile_shot_path = str(SCREENSHOTS_DIR / "e2e_taku_studio_mobile.png")
    page.screenshot(path=mobile_shot_path, full_page=False)
    assert os.path.exists(mobile_shot_path)

    # 11. Test Diagnostic Health Modal
    diag_btn = page.locator("#btnDiagnose")
    diag_btn.click()
    diag_modal = page.locator("#diagnosticModal")
    assert diag_modal.is_visible()
    page.wait_for_selector("#diagModalBody code", timeout=10000)
    diag_body_text = page.locator("#diagModalBody").inner_text()
    assert "HEALTHY" in diag_body_text.upper() or "CONNECTED" in diag_body_text.upper()

    close_diag = page.locator("#btnCloseDiagModal")
    close_diag.click()
    assert not diag_modal.is_visible()

    page.close()


def test_standalone_sandbox_page(studio_server, browser_context):
    page = browser_context.new_page()

    # Test dynamic sandbox with preview page loading
    page.goto(f"{studio_server}/preview-sandbox.html", wait_until="domcontentloaded", timeout=10000)
    page.wait_for_selector(".mock-host-page", timeout=5000)
    assert "Taku" in page.title() or "Sandbox" in page.title()

    page.close()
