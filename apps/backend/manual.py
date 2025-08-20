import os
from typing import Dict, Any, List, Optional
import pandas as pd
import threading
from datetime import datetime
from helium_boot import _find_free_port, _cdp_ready
from dotenv import load_dotenv, find_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from manual_csv_picker import find_top_recent_product
from pathlib import Path
import sys
import subprocess
import time
from playwright.sync_api import sync_playwright
from profitcal import get_profitability_metrics
from main_loop import get_configg
from sheet_writer import _hyper, _sheets_service, _get_sheet_id_and_cols,get_sheets_config

# Load .env (override current env if present)
load_dotenv(find_dotenv(), override=True)

# === ENV ===
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "").strip()
GOOGLE_CLIENT_EMAIL = os.getenv("GOOGLE_CLIENT_EMAIL", "").strip()
GOOGLE_PRIVATE_KEY = (os.getenv("GOOGLE_PRIVATE_KEY", "") or "").replace("\\n", "\n")

USER_DATA_DIR, PROFILE_DIR, CHROME_PATH, EXT_ID, CDP_PORT = get_configg()
COL_YOUR_COMPETITOR     = 6
COL_COMP_MREV           = 7
COL_YOUR_PRICE          = 9
COL_FBA_FEES            = 11
COL_STORAGE_FEES = 13
SCOPES,  ROW_WIDTH = get_sheets_config()
# === Google Sheets Helpers ===

def _read_row(svc, title: str, row_number: int) -> List[str]:
    """Read a specific row from the sheet (1-based row number)."""
    rng = f"{title}!A{row_number}:Z{row_number}"  # Read columns A-Z
    r = svc.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=rng).execute()
    values = r.get("values", [])
    if not values:
        return []
    
    # Pad the row to at least 32 columns
    row_data = values[0]
    while len(row_data) < 32:
        row_data.append("")
    
    return row_data

def open_browser(chrome_path, user_data_dir, profile_dir, cdp_port, ext_id, popup_visible=False):
    #open browser
    chrome = Path(chrome_path)
    if not chrome.exists():
        raise FileNotFoundError(f"Chrome not found: {chrome_path}")

    udd = Path(user_data_dir); udd.mkdir(parents=True, exist_ok=True)

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

    if not popup_visible:
        try:
            popup.close()
            print("[info] Closed Helium popup tab (minimal UI).")
        except Exception:
            pass
    
    return browser, ctx, pw

def close_browser(browser, ctx, pw):
    try:
        if ctx:
            ctx.close()
        if browser:
            browser.close()
    finally:
        if pw:
            pw.stop()


def fill_in_row_with_new_values_for_country(row, column_indices, country, row_number):
    """
    Write data to specific columns in an existing row and format them with black background and white text.
    
    Args:
        row: List of values for the row (should be ROW_WIDTH length)
        column_indices: List of column indices to write and format
        country: Country sheet name (e.g., "US", "UK", etc.)
        row_number: 1-based row number to write to
    """
    try:
        svc = _sheets_service()
        
        # Get sheet metadata
        sheet_id, col_count = _get_sheet_id_and_cols(svc, country)
        
        # Convert row number to 0-based for formatting
        row0 = row_number - 1
        
        # Check if the row exists by trying to read it
        try:
            test_range = f"{country}!A{row_number}:A{row_number}"
            test_result = svc.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=test_range).execute()
            row_exists = len(test_result.get("values", [])) > 0
        except Exception:
            row_exists = False
        
        # If row doesn't exist, we need to ensure it exists by writing to it first
        if not row_exists:
            print(f"Row {row_number} doesn't exist - creating it first")
            # Write an empty row to create it
            empty_row = [""] * ROW_WIDTH
            last_col_letter = _num_to_col(ROW_WIDTH - 1)
            create_range = f"{country}!A{row_number}:{last_col_letter}{row_number}"
            svc.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=create_range,
                valueInputOption="USER_ENTERED",
                body={"values": [empty_row]},
            ).execute()
            print(f"Created row {row_number} in '{country}' sheet")
        
        # Write the specific columns to the existing row
        # We need to write only the columns that have data
        for col_idx in column_indices:
            if col_idx < len(row) and row[col_idx]:  # Only write non-empty values
                # Convert column index to letter (A, B, C, etc.)
                col_letter = _num_to_col(col_idx)
                cell_range = f"{country}!{col_letter}{row_number}"
                
                # Write the value
                svc.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=cell_range,
                    valueInputOption="USER_ENTERED",
                    body={"values": [[row[col_idx]]]},
                ).execute()
        
        # Format the written columns with black background and white text
        _format_cells_black_bg_white_font(svc, sheet_id, row0=row0, col_indices=column_indices)
        
        print(f"[SHEETS] Updated row {row_number} in '{country}' sheet with columns {column_indices}")
        
    except Exception as e:
        print(f"Error filling row with new values: {e}")
        raise

def _num_to_col(n0: int) -> str:
    """Convert 0-based column index to letter (A, B, C, etc.)"""
    n = n0 + 1
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s

def _format_cells_black_bg_white_font(svc, sheet_id: int, row0: int, col_indices: List[int]):
    """Set background black + font white for specific cells (one row)."""
    requests = []
    for c in col_indices:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row0,
                    "endRowIndex": row0 + 1,
                    "startColumnIndex": c,
                    "endColumnIndex": c + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0, "green": 0, "blue": 0},
                        "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}}
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat.foregroundColor)"
            }
        })
    svc.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": requests}
    ).execute()


def find_competitor_data(df, keyword_phrase, country, row_number, browser, MAX_RETRIES=8):

    competitor_data = find_top_recent_product(df, keyword_phrase)
    print(f"competitor_data: {competitor_data}")
    #write to sheet
    row = [""] * ROW_WIDTH
    comp_title = competitor_data["product_details"] or ""
    comp_url   = competitor_data["url"]          or ""
    comp_mrev  = competitor_data["parent_level_revenue"] or ""
    row[COL_YOUR_COMPETITOR]     = _hyper(comp_url, comp_title) if (comp_url or comp_title) else ""
    row[COL_COMP_MREV]           = comp_mrev
    fill_in_row_with_new_values_for_country(row, [COL_YOUR_COMPETITOR, COL_COMP_MREV], country, row_number)
    
    
    if comp_url != "":
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print("[Info] Getting Profitability Calculator metrics.")
                pm = get_profitability_metrics(
                    browser,
                    product_url=comp_url,
                    wait_secs=60,
                    close_all_tabs_first=False,
                    close_others_after_open=True,
                )
                print(f"prof metrics: {pm}")
                #write prof metrics to sheet
                price_text   = (pm.get("product_price", {}) or {}).get("text") or ""
                fba_text     = (pm.get("fba_fees", {}) or {}).get("text") or ""
                today = datetime.now()
                is_oct__nov_dec = today.month>=10
                if is_oct__nov_dec:
                    storage_fee_text = pm.get("storage_fee_oct_dec", {}).get("text") or ""
                else:
                    storage_fee_text = pm.get("storage_fee_jan_sep", {}).get("text") or ""

                row[COL_YOUR_PRICE]          = price_text
                row[COL_FBA_FEES]            = fba_text
                row[COL_STORAGE_FEES]        = storage_fee_text
                fill_in_row_with_new_values_for_country(row, [COL_YOUR_PRICE,COL_FBA_FEES,COL_STORAGE_FEES],country,row_number)
                return
            
            except Exception as e:
                msg = f"profitability_metrics attempt {attempt} failed: {e}"
                print("[ERROR]", msg)
                if attempt == MAX_RETRIES:
                    print("[ERROR] Profitability: max retries reached.")
    
    

def process_manual_csv(row_number: int, country: str, df: pd.DataFrame, keyword_phrase: str, browser) -> Dict[str, Any]:
    """
    Process manual CSV upload:
    1. Print df.head()
    2. Check if the specified row in the Google Sheet has empty competitor columns
    3. Return result with status and any error messages
    """
    try:
        
        print(f"=== Processing row {row_number} for country {country} with keyword phrase: {keyword_phrase} ===")
        
        # Validate inputs
        if row_number < 3:
            return {
                "success": False,
                "error": f"Row number must be a positive integer > 2 since first 2 rows DO NOT have any data, got {row_number}"
            }
        
        if not country:
            return {
                "success": False,
                "error": "Country is required"
            }
        
        if not keyword_phrase or not keyword_phrase.strip():
            return {
                "success": False,
                "error": "Keyword phrase is required"
            }
        
        # Initialize Google Sheets service
        svc = _sheets_service()
        
        # Try to read the specified row, but don't fail if it doesn't exist
        try:
            row_data = _read_row(svc, country, row_number)
            row_exists = True
        except Exception:
            # Row doesn't exist yet, that's fine - we'll create it
            row_data = [""] * 32  # Empty row with 32 columns
            row_exists = False
            print(f"Row {row_number} doesn't exist yet - will create it")
        
        # Check if competitor columns are empty (or if row is new)
        competitor_col = row_data[COL_YOUR_COMPETITOR] if len(row_data) > COL_YOUR_COMPETITOR else ""
        comp_mrev_col = row_data[COL_COMP_MREV] if len(row_data) > COL_COMP_MREV else ""
        
        print(f"Row {row_number} data:")
        print(f"  Row exists: {row_exists}")
        print(f"  Competitor column ({COL_YOUR_COMPETITOR}): '{competitor_col}'")
        print(f"  Competitor MREV column ({COL_COMP_MREV}): '{comp_mrev_col}'")
        
        # Check if both competitor columns are empty
        competitor_empty = not competitor_col or competitor_col.strip() == ""
        comp_mrev_empty = not comp_mrev_col or comp_mrev_col.strip() == ""
        
        if competitor_empty and comp_mrev_empty:
            print("✓ Competitor columns are empty - ready for data insertion")
            # i want to do the following part in a separate thread, i.e. it should send return message and continue this part as well
            
            find_competitor_data(df, keyword_phrase, country, row_number,browser, MAX_RETRIES=8)
            # data_thread = threading.Thread(target=find_competitor_data, args=(df, keyword_phrase, country, row_number))
            # data_thread.daemon = True
            # data_thread.start()
            
            return {
                "success": True,
                "message": f"Preparing competitor data for row {row_number} in '{country}' sheet ",    
            }
        else:
            # Build error message with existing data
            existing_data = []
            if not competitor_empty:
                existing_data.append(f"Competitor: {competitor_col}")
            if not comp_mrev_empty:
                existing_data.append(f"Competitor Monthly Revenue: {comp_mrev_col}")
            
            error_msg = f"Row {row_number} in '{country}' sheet already has competitor data: {', '.join(existing_data)}"
            print(f"✗ {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,     
            }
            
    except Exception as e:
        error_msg = f"Error processing manual CSV: {str(e)}"
        print(f"✗ {error_msg}")
        return {
            "success": False,
            "error": error_msg
        }

def process_multiple_manually(runs_data):
    browser, ctx , pw = open_browser(CHROME_PATH, USER_DATA_DIR, PROFILE_DIR, CDP_PORT, EXT_ID)
    for run in runs_data:
        df = pd.read_csv(run["csvpath"])
        result = process_manual_csv(run["row"], run["country"], df, run["keyword"],browser)
        if result["success"]:
            print(f"✅ Run passed - further processing successful")
        else:
            print(f"❌ Run failed - further processing failed")
            print(f"Error: {result.get('error', 'Unknown error')}")
    close_browser(browser, ctx, pw)

# === CLI Testing ===
if __name__ == "__main__":
    """
    Run this file directly to test the manual CSV processing:
      1) Ensure env vars are set: SPREADSHEET_ID, GOOGLE_CLIENT_EMAIL, GOOGLE_PRIVATE_KEY
      2) Ensure tabs exist: US, UK, CAN, AUS, DE, UAE
      3) python manual.py
    """
    import pandas as pd
    
    # Create a sample DataFrame for testing
    
    
    csv_path = "C:/Users/hurai/Downloads/amz.csv"
    df = pd.read_csv(csv_path)
    
    # Test parameters
    test_row_number = 6  # Make sure this row exists in your sheet
    test_country = "CAN"  # Make sure this tab exists
    test_keyword_phrase = "test product"
    
    print("=== Testing process_manual_csv ===")
    
    try:
        result = process_manual_csv(test_row_number, test_country, df, test_keyword_phrase)
        print("Result:", result)
        
        if result["success"]:
            print("✅ Test passed - CSV processing successful")
        else:
            print("❌ Test failed - CSV processing failed")
            print(f"Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

