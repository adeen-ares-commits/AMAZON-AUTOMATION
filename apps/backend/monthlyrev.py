# monthlyrev.py
import os, re, time, csv
from datetime import datetime
from typing import Optional, Dict, Any
from playwright.sync_api import Browser, Page

# ---------- ASIN helpers ----------
_ASIN_PATTERNS = [
    re.compile(r"/dp/([A-Z0-9]{10})(?:[/?]|$)", re.I),
    re.compile(r"/gp/product/([A-Z0-9]{10})(?:[/?]|$)", re.I),
    re.compile(r"[?&]asin=([A-Z0-9]{10})(?:[&#]|$)", re.I),
]

def extract_asin_from_url(url: str) -> Optional[str]:
    if not url: return None
    for rx in _ASIN_PATTERNS:
        m = rx.search(url)
        if m: return m.group(1).upper()
    return None

def extract_asin_from_dom(page: Page) -> Optional[str]:
    # Try canonical <link> or any obvious meta/element with ASIN
    try:
        href = page.eval_on_selector("link[rel='canonical']", "el => el?.href || ''")
        asin = extract_asin_from_url(href or "")
        if asin: return asin
    except Exception:
        pass
    # Try a data attribute Helium/Amazon sometimes expose
    try:
        cand = page.eval_on_selector(":root", "d => window?.ue?.mid || ''")  # harmless probe
    except Exception:
        cand = None
    return None  # URL route is usually enough

# ---------- XRAY page locator (same strategy as competitors) ----------
def _find_xray_page(browser: Browser, timeout_ms: int = 2000) -> Optional[Page]:
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if "amazon." not in pg.url:
                    continue
                # Prefer detecting the XRAY overlay text; fall back to Export button
                try:
                    pg.get_by_text("Xray", exact=False).first.wait_for(timeout=400)
                    return pg
                except Exception:
                    pass
                try:
                    pg.get_by_role("button", name=re.compile(r"\bExport\b", re.I)).first.wait_for(timeout=300)
                    return pg
                except Exception:
                    pass
        time.sleep(0.15)
    return None

# ---------- click helper ----------
def _click_like_a_human_then_programmatic(page: Page, loc) -> bool:
    try: loc.scroll_into_view_if_needed(timeout=1500)
    except Exception: pass
    try:
        loc.click(timeout=1500); return True
    except Exception:
        try:
            el = loc.element_handle()
            if el:
                page.evaluate("(el)=>el.click()", el); return True
        except Exception:
            return False
    return False

def scrape_parent_level_revenue_from_page(page: Page) -> Optional[Dict[str, Any]]:
    """
    Scrape 'Parent Level Revenue' directly from the XRAY table on the page.
    Returns dict with keys:
      { "parent_level_revenue_text": str, "parent_level_revenue": float }
    or None if not found.
    """
    # Try to ensure the column header exists (not strictly required, but helpful)
    try:
        page.locator(
            "[data-table-name='xray-amazon-table'][data-field-name='estMonthlyRevenue']"
        ).first.wait_for(timeout=4000)
    except Exception:
        print("[WARN] 'Parent Level Revenue' header not confirmed; continuing to value cell lookup.")

    # Primary selector from your HTML
    value_loc = page.locator("[data-testid='table-cell-estMonthlyRevenue']").first
    try:
        value_loc.wait_for(state="visible", timeout=5000)
        txt = value_loc.inner_text().strip()
        num = _parse_money_to_float(txt)
        print(f"[SUCCESS] Scraped Parent Level Revenue from DOM: text={txt} parsed={num}")
        return {"parent_level_revenue_text": txt, "parent_level_revenue": num}
    except Exception as e:
        print("[ERROR] Could not scrape Parent Level Revenue from DOM:", e)
        return None


# ---------- export flow ----------
def _export_csv(page: Page, download_dir: str) -> Optional[str]:
    import os, re
    from datetime import datetime

    os.makedirs(download_dir, exist_ok=True)

    # Open Export
    export_btn = page.get_by_role("button", name=re.compile(r"\bExport\b", re.I))
    try:
        export_btn.click(timeout=2000)
    except Exception:
        page.locator(
            "button:has-text('Export'), .sc-eoEtVK:has-text('Export'), "
            ".sc-ePzlA-D:has-text('Export'), :is(button,div,span,a)[role='button']:has-text('Export')"
        ).first.evaluate("el=>el.click()")
    print("[INFO] Export menu opened.")

    # Find CSV tile
    menu_root = page.locator("div.sc-eWhHU").filter(has=page.locator("div.sc-brSOsn")).first
    try:
        menu_root.wait_for(timeout=5000)
    except Exception:
        menu_root = None
        print("[WARN] .sc-eWhHU not visible; searching CSV tile globally.")

    try:
        if menu_root:
            csv_tile = menu_root.locator("div.sc-brSOsn", has_text=re.compile(r"\bCSV\b", re.I)).first
            csv_tile.wait_for(state="visible", timeout=2500)
        else:
            csv_tile = page.locator("div.sc-brSOsn", has_text=re.compile(r"\bCSV\b", re.I)).first
            csv_tile.wait_for(state="visible", timeout=3000)
    except Exception:
        csv_tile = page.locator(
            ":is(div,button,span,a):has-text('as a CSV file'), :is(div,button,span,a):has-text('CSV')"
        ).first
        csv_tile.wait_for(state="visible", timeout=3000)

    # Native download only (no sniff)
    try:
        with page.expect_download(timeout=15000) as dl_info:
            if not _click_like_a_human_then_programmatic(page, csv_tile):
                raise RuntimeError("CSV tile click failed")
        download = dl_info.value
        suggested = download.suggested_filename or "xray_export.csv"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(suggested)
        save_as = os.path.join(download_dir, f"{base}_{stamp}{ext or '.csv'}")
        download.save_as(save_as)
        print(f"[SUCCESS] Downloaded CSV to: {save_as}")
        return save_as
    except Exception as e:
        print("[ERROR] CSV export failed (native download not captured):", e)
        return None


def _norm(s: str) -> str:
    """Normalize header names for forgiving matching."""
    return re.sub(r'[^a-z0-9]+', '', (s or '').lower())

def _parse_money_to_float(txt: Optional[str]) -> Optional[float]:
    """Turn '$12,345.67' into 12345.67; return None on failure."""
    if not txt:
        return None
    # keep digits, . and - only
    num = re.sub(r'[^0-9.\-]', '', txt)
    try:
        return float(num)
    except Exception:
        return None

def find_parent_level_revenue(csv_path: str, target_asin: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    From the Helium XRAY CSV, find the row whose ASIN == target_asin and
    return asin, file_name, product_url, and parent level revenue (text + number).
    """
    if not target_asin:
        return None
    target_asin = target_asin.strip().upper()

    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        dr = csv.DictReader(f)
        if not dr.fieldnames:
            return None

        # Build a normalized header map
        header_map = { _norm(h): h for h in dr.fieldnames }

        asin_col = header_map.get('asin')
        url_col  = header_map.get('url')
        # Be tolerant to spacing or unicode: "Parent Level Revenue"
        plr_col  = None
        for k, v in header_map.items():
            if k in ('parentlevelrevenue', 'parentrevenue', 'parentlvlrevenue'):
                plr_col = v; break
        if not (asin_col and url_col and plr_col):
            # If any key is missing, try fuzzy search
            def find_like(needle):
                for raw in dr.fieldnames:
                    if _norm(raw) == needle:
                        return raw
                return None
            asin_col = asin_col or find_like('asin')
            url_col  = url_col  or find_like('url')
            plr_col  = plr_col  or find_like('parentlevelrevenue')

        if not (asin_col and url_col and plr_col):
            return None

        for row in dr:
            asin_val = (row.get(asin_col) or '').strip().upper()
            if asin_val == target_asin:
                revenue_txt = (row.get(plr_col) or '').strip()
                revenue_num = _parse_money_to_float(revenue_txt)
                product_url = (row.get(url_col) or '').strip()
                return {
                    "asin": target_asin,
                    "file_name": os.path.basename(csv_path),
                    "product_url": product_url,
                    "parent_level_revenue": revenue_num,        # numeric (float) if parseable, else None
                    "parent_level_revenue_text": revenue_txt,   # original text e.g. "$12,345"
                }

    return None



# ---------- public API ----------
def run_monthlyrev(
    browser: Browser,
    *,
    download_dir: str = None
) -> Dict[str, Any]:
    """
    Find the XRAY product page, extract ASIN, then:
      1) Try CSV export and parse Parent Level Revenue for this ASIN.
      2) If CSV fails, scrape Parent Level Revenue directly from DOM.
    Return the same structure; if DOM fallback is used, keep CSV-related fields empty.
    """
    if download_dir is None:
        download_dir = os.path.join(os.getcwd(), "exports", "monthlyrev")

    page = _find_xray_page(browser, timeout_ms=4000)
    if not page:
        raise RuntimeError("XRAY not detected on any Amazon tab (monthlyrev).")

    page.bring_to_front()
    page.wait_for_timeout(300)

    # Extract ASIN
    asin = extract_asin_from_url(page.url) or extract_asin_from_dom(page)
    if not asin:
        for _ in range(10):
            time.sleep(0.4)
            asin = extract_asin_from_url(page.url) or extract_asin_from_dom(page)
            if asin: break

    # Try CSV path
    csv_path = _export_csv(page, download_dir)
    if csv_path:
        summary = find_parent_level_revenue(csv_path, asin)
        if summary:
            print("[INFO] CSV parsed successfully for ASIN:", asin)
            print("parent_level_revenue_text", summary.get("parent_level_revenue_text"))
            return {
                "asin": asin,
                "file_name": os.path.basename(csv_path),
                "product_url": summary.get("product_url"),
                "parent_level_revenue": summary.get("parent_level_revenue"),
                "parent_level_revenue_text": summary.get("parent_level_revenue_text"),
                "source_url": page.url,
                "saved_csv": csv_path,
                "scraped_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "module": "monthlyrev",
            }
        else:
            print("[WARN] ASIN not found in CSV or revenue column missing; falling back to DOM scrape.")

    # DOM fallback (CSV missing or didn’t contain ASIN)
    print("[FALLBACK] Scraping Parent Level Revenue directly from the page…")
    dom = scrape_parent_level_revenue_from_page(page)
    if dom:
        # Keep CSV fields empty as requested
        return {
            "asin": asin,
            "file_name": "",
            "product_url": "",
            "parent_level_revenue": dom.get("parent_level_revenue"),
            "parent_level_revenue_text": dom.get("parent_level_revenue_text"),
            "source_url": page.url,
            "saved_csv": "",
            "scraped_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "module": "monthlyrev",
        }

    # If both paths fail, raise with a clear error
    raise RuntimeError("Could not acquire Parent Level Revenue via CSV or DOM.")
