# get_category_rev.py
import re, time
from typing import Optional, Tuple, Dict
from playwright.sync_api import Browser, Page

def _clean(s: Optional[str]) -> str:
    import re
    return re.sub(r"\s+", " ", s or "").strip()

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

def _click_load_more(page: Page) -> bool:
    """Try multiple strategies to click 'Load More'. Return True if clicked."""
    clicked = False
    load_more = page.get_by_role("button", name=re.compile(r"^\s*Load More\s*$", re.I))
    try:
        load_more.wait_for(timeout=4000)
        load_more.scroll_into_view_if_needed()
        try:
            load_more.click(timeout=1500)
            print("[INFO] Load More clicked (normal).")
            return True
        except Exception:
            el = load_more.element_handle()
            if el:
                page.evaluate("(el)=>el.click()", el)
                print("[INFO] Load More clicked (programmatic).")
                return True
    except Exception:
        # fallback selector
        try:
            load_more = page.locator("button:has-text('Load More')").first
            load_more.scroll_into_view_if_needed()
            el = load_more.element_handle()
            if el:
                page.evaluate("(el)=>el.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}))", el)
                print("[INFO] Load More clicked (dispatchEvent fallback).")
                return True
        except Exception:
            pass
    return clicked

# def _extract_total_revenue(page: Page) -> Tuple[str, str]:
#     """Find the 'Total Revenue' label and extract the nearest numeric value."""
#     label = page.get_by_text("Total Revenue", exact=True).first
#     label.wait_for(timeout=5000)
#     el = label.element_handle()
#     if not el:
#         raise RuntimeError("Couldn't get handle for 'Total Revenue' label.")

#     value_text = page.evaluate(
#         """
#         (labelEl) => {
#           function findValueWithin(root) {
#             const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
#             while (walker.nextNode()) {
#               const n = walker.currentNode;
#               const txt = (n.innerText || "").trim();
#               if (!txt) continue;
#               if (/^\\$?\\s*\\d[\\d,]*(?:\\.\\d+)?$/.test(txt) && !/total\\s*revenue/i.test(txt)) {
#                 return txt;
#               }
#             }
#             return null;
#           }
#           let root = labelEl.parentElement;
#           for (let i = 0; i < 5 && root; i++) {
#             const val = findValueWithin(root);
#             if (val) return val;
#             root = root.parentElement;
#           }
#           return null;
#         }
#         """,
#         el
#     )
#     if not value_text:
#         raise RuntimeError("Couldn't locate the Total Revenue value near the label.")
#     value_text = _clean(value_text)
#     number_only = re.sub(r"[^0-9.]", "", value_text)
#     return value_text, number_only



def _extract_total_revenue(page: Page) -> Tuple[str, str]:
    # 1) Anchor on the label (case-insensitive)
    label = page.get_by_text(re.compile(r"^\s*Total\s+Revenue\s*$", re.I)).first
    label.wait_for(timeout=8000)

    # 2) Value is directly BELOW the label and NEAR it (not to the right tile)
    value = page.locator(
        "div.sc-iYRSqv.jktLat"
        ":below(:text('Total Revenue'))"
        ":near(:text('Total Revenue'), 140)"   # keep it close to the label
    ).first

    try:
        value.wait_for(state="visible", timeout=3000)
        value_text = value.inner_text().strip()
    except Exception:
        # 3) Geometry fallback: pick the closest currency-looking text **below** the label
        el = label.element_handle()
        if not el:
            raise RuntimeError("Couldn't get handle for 'Total Revenue' label.")
        value_text = page.evaluate(
            """
            (labelEl) => {
              const rectL = labelEl.getBoundingClientRect();
              const centerLX = rectL.left + rectL.width/2;
              const isVisible = (el) => {
                if (!el) return false;
                const cs = getComputedStyle(el);
                if (cs.display === 'none' || cs.visibility === 'hidden') return false;
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
              };
              // Currency-ish text (any symbol/code + grouped digits + optional decimal + K/M/B)
              const RE = /^(?:\\p{Sc}|USD|GBP|EUR|CAD|AUD|AED|د\\.?إ|A\\$|AU\\$|C\\$|CA\\$)?\\s*\\d[\\d\\s',.\\u00A0\\u202F\\u2009\\u2007\\u2060]*(?:[.,]\\d+)?\\s*(?:[KMB])?$/iu;

              const cands = Array.from(document.querySelectorAll('div.sc-iYRSqv.jktLat, div, span, p, b, strong, em'))
                .filter(isVisible)
                .map(e => {
                  const t = (e.innerText || '').trim();
                  const r = e.getBoundingClientRect();
                  return {e, t, r};
                })
                .filter(o => o.t && RE.test(o.t) && o.r.top >= rectL.bottom - 2) // strictly below label
                // keep nearby only
                .filter(o => (o.r.top - rectL.bottom) <= 200 && Math.abs((o.r.left + o.r.width/2) - centerLX) <= 180)
                .sort((a,b) => {
                  // prioritize smallest vertical gap, then total distance
                  const dyA = Math.max(0, a.r.top - rectL.bottom);
                  const dyB = Math.max(0, b.r.top - rectL.bottom);
                  if (dyA !== dyB) return dyA - dyB;
                  const cxA = a.r.left + a.r.width/2, cyA = a.r.top + a.r.height/2;
                  const cxB = b.r.left + b.r.width/2, cyB = b.r.top + b.r.height/2;
                  const dA = Math.hypot(cxA - centerLX, cyA - rectL.bottom);
                  const dB = Math.hypot(cxB - centerLX, cyB - rectL.bottom);
                  return dA - dB;
                });

              return cands.length ? cands[0].t : null;
            }
            """,
            el
        )

    if not value_text:
        raise RuntimeError("Couldn't locate the Total Revenue value near the label.")

    value_text = _clean(value_text)            # your helper
    number_only = _normalize_currency_number(value_text)  # your locale-aware normalizer
    return value_text, value_text

def _normalize_currency_number(s: str) -> str:
    """
    Normalize '£605,607', '€605.607', '605 607', 'AED 1,2M', '$1.2B' -> '605607' or scaled.
    Handles:
      - currency symbols or codes anywhere
      - thousand separators: space/NBSP/thin/apostrophe/comma/dot
      - decimal comma or dot
      - K/M/B suffix
    """
    s = s.strip()

    # Extract suffix (K/M/B)
    suffix_match = re.search(r'([KMB])\s*$', s, flags=re.I)
    mult = 1
    if suffix_match:
        mult = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}[suffix_match.group(1).upper()]
        s = s[:suffix_match.start()].strip()

    # Keep only digits, commas, dots, and common spaces/apostrophes as potential separators
    cleaned = re.sub(r"[^\d\.,\u0020\u00A0\u202F\u2009\u2007\u2060']", "", s)

    # Normalize all spaces/apostrophes to a plain space
    cleaned = re.sub(r"[\u00A0\u202F\u2009\u2007\u2060']", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Detect decimal separator: last occurrence of [.,] that has digits on both sides.
    last_sep = None
    for m in re.finditer(r"[.,]", cleaned):
        i = m.start()
        if i > 0 and i < len(cleaned) - 1 and cleaned[i-1].isdigit() and cleaned[i+1].isdigit():
            last_sep = i

    # Remove thousands separators:
    # - If we detected a decimal separator at 'last_sep', treat any other [., and spaces] as thousands.
    # - If no decimal, treat all commas/dots/spaces as thousands.
    if last_sep is not None:
        dec_char = cleaned[last_sep]
        int_part = re.sub(r"[^\d]", "", cleaned[:last_sep])
        frac_part = re.sub(r"[^\d]", "", cleaned[last_sep+1:])
        num_str = f"{int_part}.{frac_part}" if frac_part else int_part
        val = float(num_str)
    else:
        int_part = re.sub(r"[^\d]", "", cleaned)
        val = float(int_part or "0")

    val *= mult
    return str(int(round(val)))


def get_category_revenue(browser: Browser, *, wait_after_click_ms: int = 15000) -> Dict[str, str]:
    """
    Uses an existing Playwright Browser to:
      - find the XRAY page
      - click 'Load More' (best effort)
      - read 'Total Revenue' (both text and numeric)
    Returns: {'text': <e.g. '$123,456'>, 'number': <e.g. '123456'>}
    """
    page = _find_xray_page(browser, timeout_ms=1200)
    if not page:
        raise RuntimeError("XRAY not detected on any Amazon tab.")
    page.bring_to_front()
    page.wait_for_timeout(500)

    if _click_load_more(page):
        print("[INFO] Waiting 30s for data to refresh…")
        page.wait_for_timeout(30000)
    else:
        print("[WARN] Could not click 'Load More' (overlay likely intercepting). Continuing anyway.")

    value_text, number_only = _extract_total_revenue(page)
    print(f"[RESULT] Total Revenue: {value_text}  |  number: {number_only}")
    return {"text": value_text, "number": number_only, "page": page}


