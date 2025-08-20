from playwright.sync_api import TimeoutError as PwTimeout
import os, time

CEREBRO_PATH_FRAGMENT = "cerebro/index-extension"

def open_amazon_page(ctx, url: str, wait_until: str = "domcontentloaded"):
    """Open an Amazon product page in the existing context and return the Page."""
    pg = ctx.new_page()
    pg.goto(url, wait_until=wait_until)
    pg.bring_to_front()
    return pg

def _wait_for_url_contains(page, needle: str, timeout_ms: int = 30000):
    page.wait_for_url(lambda u: needle in str(u), timeout=timeout_ms)

def open_cerebro_from_xray(browser, amazon_page, asin: str, timeout_s: int = 60):
    """
    Clicks the Cerebro link on the product page and returns the Cerebro Page.
    Handles both popup (new tab) and same-tab navigation.
    """
    link_sel = f'a[href*="{CEREBRO_PATH_FRAGMENT}?asin={asin}"]'
    cerebro_link = amazon_page.locator(link_sel)
    cerebro_link.wait_for(state="visible", timeout=20_000)

    new_tab = None
    try:
        with amazon_page.expect_popup(timeout=8_000) as popup_info:
            cerebro_link.click()
        new_tab = popup_info.value
    except PwTimeout:
        # Likely same-tab navigation
        cerebro_link.click()

    if new_tab:
        try:
            new_tab.wait_for_load_state("domcontentloaded", timeout=15_000)
        except PwTimeout:
            pass
        try:
            _wait_for_url_contains(new_tab, CEREBRO_PATH_FRAGMENT, timeout_ms=20_000)
        except PwTimeout:
            # last resort: scan all pages
            candidates = [pg for c in browser.contexts for pg in c.pages
                          if CEREBRO_PATH_FRAGMENT in pg.url]
            if candidates:
                new_tab = candidates[-1]
            else:
                # dump open pages for debugging
                for c in browser.contexts:
                    for pg in c.pages:
                        print(" - open page:", pg.url)
                raise RuntimeError("Cerebro tab not found after popup.")
        new_tab.bring_to_front()
        return new_tab
    else:
        # same-tab
        try:
            _wait_for_url_contains(amazon_page, CEREBRO_PATH_FRAGMENT, timeout_ms=timeout_s * 1000)
            amazon_page.bring_to_front()
            return amazon_page
        except PwTimeout:
            candidates = [pg for c in browser.contexts for pg in c.pages
                          if CEREBRO_PATH_FRAGMENT in pg.url]
            if candidates:
                tab = candidates[-1]
                tab.bring_to_front()
                return tab
            for c in browser.contexts:
                for pg in c.pages:
                    print(" - open page:", pg.url)
            raise RuntimeError("Cerebro page not detected in same-tab or elsewhere.")

def cerebro_search(cerebro_page, keyword: str):
    """Type the keyword in Cerebro and wait for results to be ready."""
    search_input = cerebro_page.locator('input[name="phrase"]')
    search_input.wait_for(state="visible", timeout=30_000)
    time.sleep(0.5)
    search_input.fill(keyword)
    time.sleep(0.2)
    search_input.press("Enter")

    # Wait until results UI is ready (export button visible)
    cerebro_page.wait_for_selector('button[data-testid="exportdata"]',
                                   state="visible", timeout=60_000)
    time.sleep(0.5)

def export_cerebro_csv(cerebro_page, download_dir: str, filename_hint: str = None) -> str:
    """
    Opens export menu and downloads CSV. Returns absolute file path.
    Uses expect_download for reliable capture.
    """
    os.makedirs(download_dir, exist_ok=True)

    export_button = cerebro_page.locator('button[data-testid="exportdata"]')
    export_button.wait_for(state="visible", timeout=30_000)
    export_button.click()
    time.sleep(0.4)

    # Ensure the CSV tile is visible before we arm expect_download
    cerebro_page.wait_for_selector('div[data-testid="csv"]', state="visible", timeout=15_000)

    with cerebro_page.expect_download(timeout=120_000) as dl_info:
        cerebro_page.locator('div[data-testid="csv"]').click()

    download = dl_info.value
    suggested = download.suggested_filename or "cerebro.csv"

    if filename_hint:
        # keep extension from suggested if missing in hint
        root, ext = os.path.splitext(suggested)
        if os.path.splitext(filename_hint)[1]:
            out_name = filename_hint
        else:
            out_name = filename_hint + (ext or ".csv")
    else:
        out_name = suggested

    out_path = os.path.join(download_dir, out_name)
    download.save_as(out_path)
    return out_path
