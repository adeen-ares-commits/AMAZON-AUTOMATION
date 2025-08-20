# competitors.py
import os, re, time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from playwright.sync_api import Browser, Page
from csv_picker import find_top_recent_product,filter_next_product


# ---------- helpers ----------
def _find_xray_page(browser: Browser, timeout_ms: int = 1500) -> Optional[Page]:
    """Return the Amazon tab that actually has the XRAY overlay text visible."""
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "amazon." not in pg.url:
                continue
            try:
                pg.get_by_text("Xray", exact=False).first.wait_for(timeout=timeout_ms)
                return pg
            except Exception:
                pass
    return None

def _click_like_a_human_then_programmatic(page: Page, loc) -> bool:
    """Try normal click, then JS click if needed. Return True if clicked."""
    try:
        loc.scroll_into_view_if_needed()
    except Exception:
        pass
    try:
        loc.click(timeout=1500)
        return True
    except Exception:
        try:
            el = loc.element_handle()
            if el:
                page.evaluate("(el)=>el.click()", el)
                return True
        except Exception:
            return False
    return False

def _extract_total_revenue(page: Page) -> Tuple[str, str]:
    """Find the 'Total Revenue' label and extract the nearest numeric value."""
    label = page.get_by_text("Total Revenue", exact=True).first
    label.wait_for(timeout=5000)
    el = label.element_handle()
    if not el:
        raise RuntimeError("Couldn't get handle for 'Total Revenue' label.")

    value_text = page.evaluate(
        """
        (labelEl) => {
          function findValueWithin(root) {
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
            while (walker.nextNode()) {
              const n = walker.currentNode;
              const txt = (n.innerText || "").trim();
              if (!txt) continue;
              if (/^\\$?\\s*\\d[\\d,]*(?:\\.\\d+)?$/.test(txt) && !/total\\s*revenue/i.test(txt)) {
                return txt;
              }
            }
            return null;
          }
          let root = labelEl.parentElement;
          for (let i = 0; i < 5 && root; i++) {
            const val = findValueWithin(root);
            if (val) return val;
            root = root.parentElement;
          }
          return null;
        }
        """,
        el
    )
    if not value_text:
        raise RuntimeError("Couldn't locate the Total Revenue value near the label.")
    value_text = re.sub(r"\s+", " ", value_text).strip()
    number_only = re.sub(r"[^0-9.]", "", value_text)
    return value_text, number_only


# ---------- main function ----------
def run_competitors_flow(
    browser: Browser,
    *,
    download_dir: str = r"E:\automation\exports",
    max_input_visible_index: int = 7,   # 8th visible "Max" input
    max_value: str = "1000",
    title_keyword: str = "candy",
    wait_after_apply_ms: int = 8000,
    picker_within_years: int = 2,
    try_read_updated_revenue: bool = True,
    page = None
) -> Dict[str, Any]:
    """
    Uses an existing Playwright Browser to:
      1) find the XRAY page
      2) open Filters
      3) set the Nth visible 'Max' input to max_value
      4) set Title Keyword Search to `title_keyword`
      5) Apply Filters and wait
      6) Export -> CSV (native download or response-sniff fallback)
      7) Run csv_picker.find_top_recent_product on the CSV
      8) (optional) read updated 'Total Revenue' again

    Returns a dict with keys:
      {
        "downloaded_path": <str | None>,
        "picker_best": <dict | None>,
        "updated_total_revenue_text": <str | None>,
        "updated_total_revenue_number": <str | None>
      }
    """
    # # 1) locate XRAY page
    # page = _find_xray_page(browser, timeout_ms=1200)
    # if not page:
    #     raise RuntimeError("XRAY not detected on any Amazon tab.")
    # page.bring_to_front()
    # page.wait_for_timeout(400)


    # 5) EXPORT -> CSV
    os.makedirs(download_dir, exist_ok=True)
    export_btn = page.get_by_role("button", name=re.compile(r"\bExport\b", re.I))
    try:
        export_btn.click(timeout=2000)
    except Exception:
        page.locator("button:has-text('Export'), .sc-eoEtVK:has-text('Export')").first.evaluate("el=>el.click()")
    print("[INFO] Export menu opened.")

    # print("found csv tile")
    csv_tile = page.locator("div.sc-brSOsn").filter(has_text="...as a CSV file")
    downloaded_path = None
    downloaded = False
    try:
        with page.expect_download(timeout=15000) as dl_info:
            # pass
        #     try:
        #         print("scrolling into view")
        #         csv_tile.scroll_into_view_if_needed()
        #     except Exception:
        #         print("[WARN] Couldn't scroll into view for CSV tile.")
        #         pass
            if not _click_like_a_human_then_programmatic(page, csv_tile):
                raise Exception("CSV tile click failed")
        download = dl_info.value
        suggested = download.suggested_filename or "xray_export.csv"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(suggested)
        save_as = os.path.join(download_dir, f"{base}_{stamp}{ext or '.csv'}")
        # print(base,ext,save_as)
        download.save_as(save_as)
        print(f"[success] Downloaded CSV to: {save_as}")
        downloaded_path = save_as
        downloaded = True
    except Exception as e:
        print("[WARN] Native download event not seen, trying response-sniff method…", e)

    if not downloaded:
        # try again and sniff response
        try:
            _click_like_a_human_then_programmatic(page, csv_tile)
        except Exception:
            pass

        def _looks_like_csv(resp):
            try:
                if not resp.ok:
                    return False
                ctype = (resp.headers.get("content-type", "") or "").lower()
                dispo = (resp.headers.get("content-disposition", "") or "").lower()
                return ("text/csv" in ctype) or ("attachment" in dispo and "csv" in dispo)
            except Exception:
                return False

        resp = page.wait_for_event("response", timeout=20000, predicate=_looks_like_csv)
        body = resp.body()

        fname = "xray_export_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"
        m = re.search(r'filename="?([^";]+)"?', resp.headers.get("content-disposition", "") or "")
        if m:
            fname = m.group(1)
            if not fname.lower().endswith(".csv"):
                fname += ".csv"

        downloaded_path = os.path.join(download_dir, fname)
        with open(downloaded_path, "wb") as f:
            f.write(body)
        print(f"[success] Saved CSV via response sniffing: {downloaded_path}")

    # 6) Pick best product from CSV
    picker_best = None
    next_prod = None
    if downloaded_path:
        picker_best = find_top_recent_product(downloaded_path, title_keyword, within_years=picker_within_years)
        if not picker_best:
            print("[INFO] No qualifying product found in CSV.")
            next_prod = filter_next_product(downloaded_path, title_keyword)
        else:
            print("[INFO] Top recent product:", picker_best.get("product_details"))
            print("       URL:", picker_best.get("url"))
            print("       Parent Revenue:", picker_best.get("parent_level_revenue"))
            print("       Creation Date:", picker_best.get("creation_date"))
    else:
        print("[ERROR] No CSV file was downloaded.")

    # 7) (optional) read updated Total Revenue again
    updated_text = None
    updated_num = None
    if try_read_updated_revenue:
        try:
            updated_text, updated_num = _extract_total_revenue(page)
            print(f"[INFO] Updated Total Revenue: {updated_text} | number: {updated_num}")
        except Exception as e:
            print("[WARN] Total Revenue read failed:", e)

    return {
        "downloaded_path": downloaded_path,
        "picker_best": picker_best,
        "updated_total_revenue_text": updated_text,
        "updated_total_revenue_number": updated_num,
        "next_product": next_prod
    }
