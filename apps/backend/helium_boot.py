import sys, time, socket, subprocess
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PWTimeout

def _wait_for_xray_panel(page, timeout_ms: int = 20000) -> bool:
    """
    Return True when the Xray overlay + some grid text is visible.
    """
    try:
        page.wait_for_selector("#h10-style-container .react-draggable.resizable",
                               state="visible", timeout=timeout_ms)
    except PWTimeout:
        return False

    # Try a few headers that typically appear
    for header in ("BSR", "Revenue", "Price"):
        try:
            page.wait_for_selector(f"text={header}", state="visible", timeout=2500)
            return True
        except PWTimeout:
            continue
    # Panel is visible; headers not found yet—consider it OK to proceed
    return True


def _open_xray_via_widget(page, *, inject_settle_ms: int = 1500, menu_timeout_ms: int = 15000,
                          panel_timeout_ms: int = 20000) -> bool:
    """
    Hover the left Helium widget, click 'Xray — Amazon Product Research', wait for panel.
    Returns True if panel detected; False otherwise.
    """
    # Let extension inject
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(inject_settle_ms)

    # Hover the small widget to reveal the menu
    try:
        widget_svg = page.locator("#h10-page-widget svg").first
        widget_svg.wait_for(state="visible", timeout=menu_timeout_ms)
    except PWTimeout:
        return False

    box = widget_svg.bounding_box()
    if not box:
        return False

    page.mouse.move(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
    widget_svg.hover(force=True)
    page.wait_for_timeout(300)
    page.mouse.move(box["x"] + box["width"]/2, box["y"] + 6)
    page.wait_for_timeout(120)

    # Ensure the menu appeared; fallback to synthetic mouseenter if needed
    try:
        page.wait_for_selector('text=Xray — Amazon Product Research', state='visible', timeout=2500)
    except PWTimeout:
        try:
            page.evaluate("""sel => {
                const el = document.querySelector(sel);
                if (el) el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
            }""", "#h10-page-widget svg")
            page.wait_for_selector('text=Xray — Amazon Product Research', state='visible', timeout=5000)
        except PWTimeout:
            return False

    # Click the button (role-based first; text fallback)
    try:
        btn = page.get_by_role("button", name="Xray — Amazon Product Research")
        if btn.is_visible():
            btn.click()
        else:
            page.locator("div", has_text="Xray — Amazon Product Research").first.click()
    except Exception:
        return False

    return _wait_for_xray_panel(page, timeout_ms=panel_timeout_ms)


def _open_xray_via_extension(ctx, *, ext_id: str, target_url: str,
                             popup_visible: bool = False, wait_secs: int = 20):
    """
    Use the extension popup to instruct Helium to open the Amazon results page and run Xray.
    Returns (page or None). Does NOT guarantee panel visibility—only opens the tab.
    """
    popup_url = f"chrome-extension://{ext_id}/popup.html"
    popup = ctx.new_page()
    popup.goto(popup_url, wait_until="domcontentloaded")
    try:
        popup.evaluate(
            """(targetUrl) => new Promise((resolve) => {
                chrome.runtime.sendMessage(
                    { type: "open-page-and-xray", params: { url: targetUrl } },
                    () => resolve(true)
                );
                setTimeout(() => resolve(false), 50000);
            })""",
            target_url,
        )
    except Exception:
        # Popup eval can fail if service worker isn't active; treat as no-op and fallback later
        pass

    if not popup_visible:
        try: popup.close()
        except Exception: pass

    # Find the Amazon results tab Helium should have opened
    target_page = None
    deadline = time.time() + wait_secs
    while time.time() < deadline and target_page is None:
        for pg in ctx.pages:
            url = pg.url or ""
            if url.startswith("https://www.amazon.") and "/s?" in url:
                target_page = pg
                break
        if target_page:
            break
        time.sleep(0.25)

    if target_page:
        try: target_page.bring_to_front()
        except Exception: pass
    return target_page


def _find_free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]; s.close(); return port

def _cdp_ready(port: int) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False

def _click_analyze_products(page, timeout_ms: int = 30000):
    """
    Try a few resilient strategies to click the 'Analyze Products' button.
    """
    locators = [
        page.get_by_role("button", name="Analyze Products", exact=True),
        page.locator("button:has-text('Analyze Products')"),
        # last-resort: find the text node then climb to nearest button ancestor
        page.locator("text=Analyze Products").locator("xpath=ancestor::button[1]"),
    ]
    for loc in locators:
        try:
            loc.wait_for(state="visible", timeout=timeout_ms)
            # Sometimes the button sits under a sticky header; scroll into view.
            loc.scroll_into_view_if_needed(timeout=timeout_ms)
            loc.click(timeout=timeout_ms)
            print("[INFO] Clicked 'Analyze Products' button now sleeping for 20 secs.")
            time.sleep(20)
            return True
        except Exception:
            continue
    raise TimeoutError("Could not find/click 'Analyze Products' within the timeout.")


def boot_and_xray(
    *,
    chrome_path: str,
    user_data_dir: str,
    profile_dir: str = "Profile 4",
    ext_id: str,
    target_url: str,
    cdp_port: int | None = 9666,      # None => auto free port
    wait_secs: int = 20,
    popup_visible: bool = False       # open -> send -> (optionally) close
):
    """
    Launch Chrome (CDP), connect Playwright, trigger Helium XRAY for target_url,
    and return as soon as the Amazon results tab is detected.

    Returns: (playwright, browser, context, target_page)
    """
    chrome = Path(chrome_path)
    if not chrome.exists():
        raise FileNotFoundError(f"Chrome not found: {chrome_path}")

    udd = Path(user_data_dir); udd.mkdir(parents=True, exist_ok=True)
    reuse = False

    if cdp_port is None:
        cdp_port = _find_free_port()

    if not _cdp_ready(cdp_port):
        print(f"[info] Launching Chrome on port {cdp_port}...")
        args = [
            str(chrome),
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={user_data_dir}",
            f"--profile-directory={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ]
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)

        deadline = time.time() + 25
        while time.time() < deadline and not _cdp_ready(cdp_port):
            time.sleep(0.2)
        if not _cdp_ready(cdp_port):
            raise TimeoutError(f"CDP not ready on 127.0.0.1:{cdp_port}")
        print(f"[info] Chrome launched and CDP ready on {cdp_port}")
    else:
        print(f"[info] Reusing existing Chrome CDP on {cdp_port}")
        reuse=True

    cdp_url  = f"http://127.0.0.1:{cdp_port}"
    popup_url = f"chrome-extension://{ext_id}/popup.html"

    print("[info] Connecting Playwright to Chrome...")
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(cdp_url)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    # Open extension popup just to send the message
    popup = ctx.new_page()
    popup.goto(popup_url, wait_until="domcontentloaded")
    print("[info] Opened Helium popup (transient).")
    
    # Optionally hide/close popup to keep things clean
    if not popup_visible:
        try:
            popup.close()
            print("[info] Closed Helium popup.")
        except Exception:
            pass

    if reuse:
        # Close all existing pages in the context without closing the browser
        for page in ctx.pages:
            try:
                page.close()
            except Exception as e:
                print(f"[warn] Could not close page: {e}")

    # 2) Open the target URL in a fresh page
    target_page = ctx.new_page()
    print(f"[info] Navigating to target URL: {target_url}")
    target_page.goto(target_url, wait_until="domcontentloaded", timeout=120_000)

    # 3) Sleep for 120 seconds (give the extension time to analyze/render)
    print("[info] Sleeping 30 seconds to allow page/extension work...")
    time.sleep(30)

    # 4) Click the 'Analyze Products' button
    print("[info] Attempting to click 'Analyze Products'...")
    _click_analyze_products(target_page, timeout_ms=45_000)
    print("[info] 'Analyze Products' clicked.")

    return pw, browser, ctx, target_page


    