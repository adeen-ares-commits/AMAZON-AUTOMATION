import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load .env (override current env if present)
load_dotenv(find_dotenv(), override=True)

# === ENV ===
SPREADSHEET_ID = None
EXISTING_SELLER_SPREADSHEET_ID = os.getenv("EXISTING_SELLER_SPREADSHEET_ID", "").strip()
NEW_SELLER_SPREADSHEET_ID= os.getenv("NEW_SELLER_SPREADSHEET_ID", "").strip()
VENDOR_SPREADSHEET_ID=os.getenv("VENDOR_SPREADSHEET_ID", "").strip()

GOOGLE_CLIENT_EMAIL = os.getenv("GOOGLE_CLIENT_EMAIL", "").strip()
GOOGLE_PRIVATE_KEY = (os.getenv("GOOGLE_PRIVATE_KEY", "") or "").replace("\\n", "\n")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# === COLUMNS (zero-indexed) ===
COL_NO                  = 0
COL_CATEGORY            = 1
COL_PRODUCTS            = 2
COL_CURRENT_MREV        = 3
COL_MONTHLY_MARKETCAP_1 = 4
# COL_YOUR_COMPETITOR     = 6
# COL_COMP_MREV           = 7
# COL_YOUR_PRICE          = 9
# COL_FBA_FEES            = 11
# COL_STORAGE_FEES = 13
COL_UNITS_20            = 18
COL_UNITS_15            = 22
COL_UNITS_10            = 26
COL_PPU_20              = 17
COL_PPU_15              = 21
COL_PPU_10              = 25
COL_REV_20              = 19
COL_REV_15              = 23
COL_REV_10              = 27

ORIGINAL_COL_UNITS_20          = 18
ORIGINAL_COL_UNITS_15          = 22
ORIGINAL_COL_UNITS_10          = 26

AFFECTED_COLS = [
    COL_UNITS_10, COL_UNITS_15, COL_UNITS_20
]

# total columns per row (0..31 inclusive) — adjust if your sheet is wider
ROW_WIDTH = 32

# Which columns we’ll format (bg black + font white) after writing:
FILLED_COLS = [
    COL_NO, COL_CATEGORY, COL_PRODUCTS, COL_CURRENT_MREV, COL_MONTHLY_MARKETCAP_1,
    # COL_YOUR_COMPETITOR, COL_COMP_MREV, COL_YOUR_PRICE, COL_FBA_FEES, COL_STORAGE_FEES,
    COL_PPU_20, COL_UNITS_20, COL_REV_20, COL_PPU_15, COL_UNITS_15, COL_REV_15, COL_PPU_10, COL_UNITS_10, COL_REV_10
]
def get_sheets_config():
    return SCOPES,  ROW_WIDTH
# === Google Sheets Helpers ===
def _sheets_service():
    if not (SPREADSHEET_ID and GOOGLE_CLIENT_EMAIL and GOOGLE_PRIVATE_KEY):
        raise RuntimeError("Missing SPREADSHEET_ID / GOOGLE_CLIENT_EMAIL / GOOGLE_PRIVATE_KEY.")
    creds = service_account.Credentials.from_service_account_info(
        {
            "type": "service_account",
            "client_email": GOOGLE_CLIENT_EMAIL,
            "private_key": GOOGLE_PRIVATE_KEY,
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)

def _esc(s: str) -> str:
    return str(s or "").replace('"', '""')

def _hyper(url: str, text: Optional[str] = "link") -> str:
    url = str(url or "")
    return f'=HYPERLINK("{_esc(url)}","{_esc(text or "link")}")' if url else ""

def _get_sheet_id_and_cols(svc, title: str):
    meta = svc.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    for sh in meta.get("sheets", []):
        props = sh.get("properties", {})
        if props.get("title") == title:
            grid = props.get("gridProperties", {}) or {}
            return props.get("sheetId"), grid.get("columnCount", ROW_WIDTH)
    raise ValueError(f'Sheet/tab "{title}" not found.')

def _first_empty_row(svc, title: str, col_letter: str = "A") -> int:
    """Find first empty row by scanning from row 1 down in the target column (returns 1-based index)."""
    rng = f"{title}!{col_letter}1:{col_letter}"
    r = svc.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=rng).execute()
    used = len(r.get("values", []) or [])
    return used + 1

def _next_no_value(svc, title: str) -> int:
    """Reads column A to get last numeric 'No.' and increments it. If none, starts at 1."""
    rng = f"{title}!A1:A"
    r = svc.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=rng).execute()
    vals = [row[0] for row in (r.get("values", []) or []) if row]
    last_num = 0
    for v in reversed(vals):
        try:
            last_num = int(str(v).strip())
            break
        except Exception:
            continue
    return last_num + 1 if last_num >= 0 else 1

def _num_to_col(n0: int) -> str:
    n = n0 + 1
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s

def _write_row(svc, title: str, row1: int, row_vals: List[str]):
    last_col_letter = _num_to_col(ROW_WIDTH - 1)
    rng = f"{title}!A{row1}:{last_col_letter}{row1}"
    svc.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=rng,
        valueInputOption="USER_ENTERED",
        body={"values": [row_vals]},
    ).execute()

def _insert_row_and_copy_template_format(
    svc, sheet_id: int, insert_row0: int, column_count: int
):
    """
    Insert a row at index insert_row0 and copy (from the template row now below it):
      - Cell format (number formats, borders, fonts, colors)
      - Formulas (without copying static values)
      - Data validation rules (optional)
      - Conditional formatting rules (optional)
    """
    src_row0 = insert_row0 + 1  # after insert, the original template is now here

    requests = [
        # 1) Insert the new row (no inheritance; we'll copy explicitly)
        {
            "insertDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": insert_row0,
                    "endIndex": insert_row0 + 1,
                },
                "inheritFromBefore": False,
            }
        },

        # 2) Copy ONLY formatting
        {
            "copyPaste": {
                "source": {
                    "sheetId": sheet_id,
                    "startRowIndex": src_row0,
                    "endRowIndex": src_row0 + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": column_count,
                },
                "destination": {
                    "sheetId": sheet_id,
                    "startRowIndex": insert_row0,
                    "endRowIndex": insert_row0 + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": column_count,
                },
                "pasteType": "PASTE_FORMAT",
                "pasteOrientation": "NORMAL",
            }
        }
    ]

    svc.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": requests}
    ).execute()


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

def _write_partial_cells(svc, title: str, row1: int, col_to_value: Dict[int, str]):
    """
    Update only the given cells in a row (1-based row index).
    Keys in col_to_value are 0-based column indices.
    """
    if not col_to_value:
        return
    data = []
    for c_idx, val in col_to_value.items():
        # Only write non-empty values; skip empty strings to preserve existing formulas
        if val == "":
            continue
        a1 = f"{title}!{_num_to_col(c_idx)}{row1}:{_num_to_col(c_idx)}{row1}"
        data.append({"range": a1, "values": [[val]]})

    if not data:
        return

    svc.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "USER_ENTERED", "data": data}
    ).execute()

def _insert_duplicate_of_last_row(svc, sheet_id: int, title: str, column_count: int) -> int:
    """
    Finds the last filled row in the sheet, inserts a new row directly *below* it,
    duplicates (values + formulas + formats) from that last row into the new row,
    and returns the new row index (1-based).
    """
    # last filled (1-based)
    first_empty_row1 = _first_empty_row(svc, title, col_letter="A")
    last_filled_row1 = first_empty_row1 - 1
    if last_filled_row1 < 1:
        # Nothing to duplicate; insert at top and just return row 1
        requests = [{
            "insertDimension": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
                "inheritFromBefore": False
            }
        }]
        svc.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": requests}).execute()
        return 1

    # We want a new row BELOW last_filled_row1
    # Insert at 0-based startIndex == last_filled_row1 to place a new row at (last_filled_row1+1) (1-based)
    insert_row0 = last_filled_row1
    new_row1 = last_filled_row1 + 1

    requests = [
        # Insert a blank row below the last filled row
        {
            "insertDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": insert_row0,
                    "endIndex": insert_row0 + 1
                },
                "inheritFromBefore": False
            }
        },
        # Copy EVERYTHING from the last filled row to the new row (values + formulas + formats)
        {
            "copyPaste": {
                "source": {
                    "sheetId": sheet_id,
                    "startRowIndex": last_filled_row1 - 1,  # 0-based
                    "endRowIndex":   last_filled_row1,      # exclusive
                    "startColumnIndex": 0,
                    "endColumnIndex": column_count
                },
                "destination": {
                    "sheetId": sheet_id,
                    "startRowIndex": new_row1 - 1,          # 0-based
                    "endRowIndex":   new_row1,
                    "startColumnIndex": 0,
                    "endColumnIndex": column_count
                },
                "pasteType": "PASTE_NORMAL",               # ← includes values, formulas, and formats
                "pasteOrientation": "NORMAL"
            }
        }
    ]

    svc.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": requests}
    ).execute()

    return new_row1


# === Row Builder ===
def _build_row_from_product(prod: Dict[str, Any],seller_type:str,country:str) -> List[str]:
    """Build a 32-column row with only specified columns filled; others empty."""
    global AFFECTED_COLS
    row = [""] * ROW_WIDTH

    productname = prod.get("productname") or ""
    url         = prod.get("url") or ""
    keyword     = prod.get("keyword") or ""
    categoryUrl = prod.get("categoryUrl") or ""
    res         = prod.get("result", {}) or {}


    # Sources
    cat_rev_text = res.get("category_revenue", {}).get("text") or ""
    monthly_meta = res.get("monthly_revenue", {}).get("meta", {}) or {}
    monthly_parent_rev_text = monthly_meta.get("parent_level_revenue_text") or ""

    # cf          = res.get("competitors_flow", {}) or {}
    # picker_best = cf.get("picker_best", {}) or {}
    # raw_result  = cf.get("raw_result", {}) or {}

    # # Fallbacks for competitor fields
    # comp_title = picker_best.get("product_details") or raw_result.get("product_details") or ""
    # comp_url   = picker_best.get("url")            or raw_result.get("url")            or ""
    # comp_mrev  = picker_best.get("parent_level_revenue") or raw_result.get("parent_level_revenue") or ""

    # pm = res.get("profitability_metrics", {}) or {}
    # price_text   = (pm.get("product_price", {}) or {}).get("text") or ""
    # fba_text     = (pm.get("fba_fees", {}) or {}).get("text") or ""
    # today = datetime.now()
    # is_oct__nov_dec = today.month>=10
    # if is_oct__nov_dec:
    #     storage_fee_text = pm.get("storage_fee_oct_dec", {}).get("text") or ""
    # else:
    #     storage_fee_text = pm.get("storage_fee_jan_sep", {}).get("text") or ""

    # GPT projections
    gp = (res.get("gpt_projection", {}) or {}).get("response", {}) or {}
    low_units  = gp.get("low_total_sales", "")
    base_units = gp.get("base_total_sales", "")
    high_units = gp.get("high_total_sales", "")
    low_revenue = gp.get("low_total_revenue", "")
    base_revenue = gp.get("base_total_revenue", "")
    high_revenue = gp.get("high_total_revenue", "")
    low_prof = gp.get("low_total_profit", "")
    base_prof = gp.get("base_total_profit_start_ads", "")
    high_prof = gp.get("high_total_profit", "")
    if low_prof != "" and low_units != "":
        low_ppu = f"${low_prof / low_units:.2f}"
    else:
        low_ppu = ""
    if base_prof != "" and base_units != "":
        base_ppu = f"${base_prof / base_units:.2f}"
    else:
        base_ppu = ""
    if high_prof != "" and high_units != "":
        high_ppu = f"${high_prof / high_units:.2f}"
    else:
        high_ppu = ""

    # print("afect cols", AFFECTED_COLS)
    # print("afect cols", AFFECTED_COLS)
    AFFECTED_COLS[0], AFFECTED_COLS[1], AFFECTED_COLS[2] = ORIGINAL_COL_UNITS_20, ORIGINAL_COL_UNITS_15, ORIGINAL_COL_UNITS_10
    if seller_type == "vendor":
        if country not in ["US", "CAN"]:
            for i,col in enumerate(AFFECTED_COLS):
                AFFECTED_COLS[i]+=3
        else:
            for i,col in enumerate(AFFECTED_COLS):
                AFFECTED_COLS[i]+=2
    elif seller_type == "existing_seller":
        if country not in ["US", "CAN", "AUS"]:
            # print("affected columns :", AFFECTED_COLS)
            for i,col in enumerate(AFFECTED_COLS):
                AFFECTED_COLS[i]+=1
            # print("affected columns :", AFFECTED_COLS)
        else:
            for i,col in enumerate(AFFECTED_COLS):
                AFFECTED_COLS[i]-=0
    else: #for new seller
        if country not in ["US", "CAN", "AUS"]:
            for i,col in enumerate(AFFECTED_COLS):
                AFFECTED_COLS[i]-=1
        else:
            for i,col in enumerate(AFFECTED_COLS):
                AFFECTED_COLS[i]-=2
    
    COL_UNITS_10, COL_UNITS_15, COL_UNITS_20 = AFFECTED_COLS[0], AFFECTED_COLS[1], AFFECTED_COLS[2]

    # Fill requested columns
    row[COL_CATEGORY]            = _hyper(categoryUrl, keyword) if categoryUrl else keyword
    row[COL_PRODUCTS]            = _hyper(url, productname) if url else productname
    row[COL_CURRENT_MREV]        = monthly_parent_rev_text
    row[COL_MONTHLY_MARKETCAP_1] = cat_rev_text


    # row[COL_YOUR_COMPETITOR]     = _hyper(comp_url, comp_title) if (comp_url or comp_title) else ""
    # row[COL_COMP_MREV]           = comp_mrev
    # row[COL_YOUR_PRICE]          = price_text
    # row[COL_FBA_FEES]            = fba_text
    # row[COL_STORAGE_FEES]        = storage_fee_text
    # row[COL_PPU_20]              = low_ppu
    # row[COL_PPU_15]              = base_ppu
    # row[COL_PPU_10]              = high_ppu
    row[COL_UNITS_20]            = str(low_units) if low_units != "" else ""
    row[COL_UNITS_15]            = str(base_units) if base_units != "" else ""
    row[COL_UNITS_10]            = str(high_units) if high_units != "" else ""
    # row[COL_REV_20]              = str(low_revenue) if low_revenue != "" else ""
    # row[COL_REV_15]              = str(base_revenue) if base_revenue != "" else ""
    # row[COL_REV_10]              = str(high_revenue) if high_revenue != "" else ""

    if seller_type == 'new_seller':
        # for new seller, we need to clear the current mrev and units columns since it has no product yet
        row[COL_PRODUCTS+1] = row[COL_PRODUCTS]   #copies this value in case of new seller
        row[COL_CURRENT_MREV] = ""
        row[COL_UNITS_10] = ""
        row[COL_UNITS_15] = ""
        row[COL_UNITS_20] = ""
    else:
        pass #handled in manual.py, uses competitor data from the CSV file

    COL_UNITS_20, COL_UNITS_15, COL_UNITS_10 = ORIGINAL_COL_UNITS_20, ORIGINAL_COL_UNITS_15, ORIGINAL_COL_UNITS_10


    return row

# === Public API ===
def write_results_to_country_tabs(json_results: Dict[str, Any]):
    """
    For each brand -> country -> product:
      - Select sheet by country name (tab must exist: US, UK, CAN, AUS, DE, UAE)
      - Find first empty row (scan from row 1)
      - INSERT a new row at that position
      - Copy FORMAT from the (now shifted) template row below into inserted row
      - Auto-increment 'No.' in col 0
      - Fill target columns (with hyperlinks + fallbacks)
      - Black background + white text on the cells we filled
      - Leave the original template row right below for the next product
    """
    global SPREADSHEET_ID
    # svc = _sheets_service()
    additional_run_data = []
    for brand_block in json_results.get("runs", []):
        sellerType = brand_block.get("seller_type")
        if sellerType == "vendor":
            SPREADSHEET_ID = VENDOR_SPREADSHEET_ID
        elif sellerType == "existing_seller":
            SPREADSHEET_ID = EXISTING_SELLER_SPREADSHEET_ID
        else:
            SPREADSHEET_ID = NEW_SELLER_SPREADSHEET_ID

        print("Updated Spread sheet id to ",SPREADSHEET_ID)
        svc = _sheets_service()

        for country_block in brand_block.get("countries", []):
            country = country_block.get("name") or ""
            if not country:
                continue

            try:
                sheet_id, col_count = _get_sheet_id_and_cols(svc, country)
                if col_count < ROW_WIDTH:
                    col_count = ROW_WIDTH
            except Exception as e:
                print(f'[WARN] Skipping country "{country}": {e}')
                continue

            for prod in country_block.get("products", []):
                # 1) Build values for this product
                print("Seller type", sellerType)
                row_vals = _build_row_from_product(prod, sellerType, country)

                # 2) Duplicate last filled row and get the new row index (1-based)
                new_row1 = _insert_duplicate_of_last_row(svc, sheet_id, country, col_count)

                # 3) Prepare selective overwrites (preserve formulas/values elsewhere)
                col_to_value = {}

                # Auto-increment "No."
                next_no = _next_no_value(svc, country)
                col_to_value[COL_NO] = str(next_no)

                # Only overwrite columns that your builder actually populated (non-empty)
                for c_idx, val in enumerate(row_vals):
                    if val not in (None, ""):
                        col_to_value[c_idx] = val

                # 4) Overwrite just those cells
                _write_partial_cells(svc, country, new_row1, col_to_value)

                # 5) Optional highlight: black bg + white font on filled columns
                _format_cells_black_bg_white_font(svc, sheet_id, row0=new_row1 - 1, col_indices=FILLED_COLS)

                print(f'[SHEETS] Duplicated last row and wrote row {new_row1} to "{country}" (No.={next_no})')

                # 6) Log run data (use new_row1; template_row1 no longer exists here)
                additional_run_data.append({
                    "row": new_row1,
                    "country": country,
                    "keyword": prod["keyword"],
                    "csvname": prod["csvFile"],
                    "csvpath": prod["csvFilePath"],
                    "seller_type": sellerType
                })

    return additional_run_data
# === Local test runner (no scraper required) ===# === Local test runner (no scraper required) ===
def main():
    """
    Run this file directly to test the writer without the scraper:
      1) Ensure env vars are set: SPREADSHEET_ID, GOOGLE_CLIENT_EMAIL, GOOGLE_PRIVATE_KEY
      2) Ensure tabs exist: US, UK, CAN, AUS, DE, UAE
      3) python sheet_writer.py
    """
    sample = {
        "runs": [
            {
                "brand": "Big wipes",
                "seller_type": "new_seller",
                "countries": [
                    {
                        "name": "UK",
                        "products": [
                            {
                                "productname": "WILSON NFL Super Grip Composite Footballs",
                                "url": "https://www.amazon.com/Wilson-Super-Grip-Official-Football/dp/B0012SNLJG",
                                "keyword": "football",
                                "categoryUrl": "https://www.amazon.com/s?k=football",
                                "csvFile" : "xyz", "csvFilePath" : "abc",
                                "result": {
                                    "category_revenue": {"text": "4,768,718", "number": "4768718"},
                                    "monthly_revenue": {"meta": {"parent_level_revenue_text": "$231,767.51"}},
                                    # "competitors_flow": {
                                    #     "picker_best": {
                                    #         "product_details": "SwimWays Hydro Waterproof Football",
                                    #         "url": "https://www.amazon.com/dp/B0CCW7Q9F5?psc=1",
                                    #         "parent_level_revenue": "83,091.29"
                                    #     },
                                    #     "raw_result": {}
                                    # },
                                    # "profitability_metrics": {
                                    #     "fba_fees": {"text": "$7.88", "number": "7.88"},
                                    #     "storage_fee_jan_sep": {"text": "$1.00", "number": "1.00"},
                                    #     "storage_fee_oct_dec": {"text": "$1.00", "number": "1.00"},
                                    #     "product_price": {"text": "12.99", "number": "12.99"}
                                    # },
                                    "gpt_projection": {
                                        "response": {
                                            "low_total_sales": 63, 
                                            "base_total_sales": 96, 
                                            "high_total_sales": 135,
                                            "low_total_revenue": 798,
                                            "base_total_revenue": 1152,
                                            "high_total_revenue": 1560,
                                            "low_total_profit": 450,
                                            "base_total_profit_start_ads": 300,
                                            "base_total_profit_end_ads": 350,
                                            "high_total_profit": 400
                                        }
                                    }
                                }
                            },
                            {
                                "productname": "Nike Academy Football FZ2966",
                                "url": "https://www.amazon.com/NIKE-Unisex-Adult-Academy-Football-Blackened/dp/B0DBLQGGWV",
                                "keyword": "soccer ball",
                                "categoryUrl": "https://www.amazon.com/s?k=soccer+ball",
                                "csvFile" : "xyz", "csvFilePath" : "abc",
                                "result": {
                                    "category_revenue": {"text": "3,337,731", "number": "3337731"},
                                    "monthly_revenue": {"meta": {"parent_level_revenue_text": "$219,553.49"}},
                                    # "competitors_flow": {
                                    #     "picker_best": {
                                    #         "product_details": "Soccer Ball Size 5 & Size 3",
                                    #         "url": "https://www.amazon.com/dp/B0CRBFNTHS?psc=1",
                                    #         "parent_level_revenue": "47,894.36"
                                    #     },
                                    #     "raw_result": {}
                                    # },
                                    # "profitability_metrics": {
                                    #     "fba_fees": {"text": "$5.87", "number": "5.87"},
                                    #     "storage_fee_jan_sep": {"text": "$1.00", "number": "1.00"},
                                    #     "storage_fee_oct_dec": {"text": "$1.00", "number": "1.00"},
                                    #     "product_price": {"text": "19.99", "number": "19.99"}
                                    # },
                                    "gpt_projection": {
                                        "response": {
                                            "low_total_sales": 225, 
                                            "base_total_sales": 343, 
                                            "high_total_sales": 483,
                                            "low_total_revenue": 4500,
                                            "base_total_revenue": 6860,
                                            "high_total_revenue": 9660,
                                            "low_total_profit": 3000,
                                            "base_total_profit_start_ads": 2000,
                                            "base_total_profit_end_ads": 2500,
                                            "high_total_profit": 3500
                                        }
                                    },
                                    "errors": []
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }

    try:
        write_results_to_country_tabs(sample)
        print("Test insert/write complete.")
    except Exception as e:
        print("Test failed:", e)

if __name__ == "__main__":
    main()
