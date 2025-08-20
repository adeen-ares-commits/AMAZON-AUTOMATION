# csv_picker.py
from __future__ import annotations
import csv
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
import pandas as pd


# --- config: match your exact CSV column names ---
COL_PRODUCT_DETAILS = "Product Details"
COL_URL             = "URL"
COL_PARENT_REVENUE  = "Parent Level Revenue"
COL_REVENUE = "Revenue"
COL_CREATION_DATE   = "Creation Date"

# Try a few common date formats you may see in exports
_DATE_FORMATS = (
    "%Y-%m-%d",        # 2025-08-01
    "%m/%d/%Y",        # 08/01/2025
    "%d/%m/%Y",        # 01/08/2025
    "%d-%b-%Y",        # 01-Aug-2025
    "%b %d, %Y",       # Aug 01, 2025
)

def _to_number(s: str) -> Optional[float]:
    """Convert currency/number like '$12,345.67' -> 12345.67; returns None if blank/invalid."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    # Handle negatives like ($123.45)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    # Remove $ and commas and spaces
    s = s.replace("$", "").replace(",", "").strip()
    if not s:
        return None
    try:
        val = float(s)
        return -val if neg else val
    except ValueError:
        return None

def _parse_date(s: str) -> Optional[datetime]:
    """Parse date using several common formats; returns None if it can't parse."""
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # Last resort: try to interpret YYYY/MM/DD (occasionally seen)
    try:
        parts = s.replace(".", "/").replace("-", "/").split("/")
        if len(parts) == 3:
            y, m, d = [int(p) for p in parts]
            if y < 100:  # unlikely but safeguard
                y += 2000
            return datetime(y, m, d)
    except Exception:
        pass
    return None


def filter_next_best_product(df, keyword_phrase,flag):
    #return the df with only one element which is latest product and includes the keyword_phrase
    df_filtered = df[df['Product Details'].str.contains(keyword_phrase, case=False)]
    if len(df_filtered) == 0:
        return df.iloc[0]
    if len(df_filtered) == 1:
        return df_filtered.iloc[0]
    if flag == 1:   #return value with most recent creation date
        df_filtered = df_filtered.sort_values(by='Creation Date', ascending=False)
    else:           #return value with least review count
        df_filtered['Review Count'] = pd.to_numeric(df_filtered['Review Count'], errors='coerce')
        df_filtered.dropna(subset=['Review Count'], inplace=True)
        df_filtered = df_filtered.sort_values(by='Review Count', ascending=True)
    return df_filtered.iloc[0]

def filter_csv_by_reviews_and_keyword(df, keyword_phrase, max_reviews=1000):
    """
    Filters input CSV rows where:
      - Review Count <= max_reviews i.e. 1000
      - Display Order column includes the keyword_phrase (case-insensitive)

    Saves filtered rows to output_csv.
    """
    filtered_rows = []
    # print(keyword_phrase.lower())

    df_filtered = df[df['Product Details'].str.contains(keyword_phrase, case=False)]
    df_filtered['Review Count'] = pd.to_numeric(df_filtered['Review Count'], errors='coerce')
    df_filtered.dropna(subset=['Review Count'], inplace=True)  # Drop any rows where the conversion failed (i.e., where 'Review Count' is NaN)
    df_filtered = df_filtered[df_filtered['Review Count'] <= max_reviews]
    # print length of df
    print(f"Filtered rows: {len(df_filtered)}")
    if len(df_filtered) == 0:
        return filter_next_best_product(df, keyword_phrase,2)

    return df_filtered

def extract_result_from_df(df_filtered):
    df_dict = df_filtered.to_dict()
    print(f"df is only one element, cant sort or filter further:")
    try:
        best_rev =  df_dict[COL_PARENT_REVENUE]
    except:
        best_rev = df_dict[COL_REVENUE]
    result = {
        "product_details": (df_dict[COL_PRODUCT_DETAILS] or "").strip(),
        "url": (df_dict[COL_URL] or "").strip(),
        "parent_level_revenue": str(best_rev or "").strip(),
        "creation_date": str(df_dict[COL_CREATION_DATE] or "").strip(),
    }
    # print(result)
    return result


def find_top_recent_product(df, keyword_phrase: str, within_years: int = 2) -> Optional[Dict[str, str]]:
    """
    Scan the CSV and return a dict with the best recent product:
    - Max 'Parent Level Revenue'
    - 'Creation Date' within last `within_years` years (approx. 365*years days)

    Returns None if no qualifying rows found.
    """
    df_filtered = filter_csv_by_reviews_and_keyword(df, keyword_phrase)
    # continue if df is DataFrame, if it is only one element, return it
    if isinstance(df_filtered, pd.Series): 
        result = extract_result_from_df(df_filtered)
        return result

    cutoff = datetime.now() - timedelta(days=365 * within_years)
    best_row = None
    best_rev = float("-inf")

    for idx,row in df_filtered.iterrows():
        # Access columns defensively

        created_at = _parse_date(row[COL_CREATION_DATE])
        if not created_at or created_at < cutoff:
            continue

        try:
            rev = _to_number(row[COL_PARENT_REVENUE])
        except:
            rev = _to_number(row[COL_REVENUE])

        if rev is None:
            continue

        if rev > best_rev:
            best_rev = rev
            best_row = row
        elif rev == best_rev and best_row:
            # Tie-breaker 1: most recent Creation Date wins
            prev_dt = _parse_date(best_row[COL_CREATION_DATE])
            if prev_dt and created_at > prev_dt:
                best_row = row
            # (Optional) add more tie-breakers if you like (e.g., higher Review Count)

    if best_row is None:
        single_item =  filter_next_best_product(df, keyword_phrase,1)
        result = extract_result_from_df(single_item)
        return result

    # Build a concise result payload (add fields as you need)
    try:
        best_rev =  best_row[COL_PARENT_REVENUE]
    except:
        best_rev = best_row[COL_REVENUE]
    result = {
        "product_details": (best_row[COL_PRODUCT_DETAILS] or "").strip(),
        "url": (best_row[COL_URL] or "").strip(),
        "parent_level_revenue": str(best_rev or "").strip(),
        "creation_date": str(best_row[COL_CREATION_DATE] or "").strip(),
        # # Handy extras you might want downstream
        # "asin": (best_row["ASIN"] or "").strip(),
        # "brand": (best_row["Brand"] or "").strip(),
        # "price": (best_row["Price  $"] or "").strip(),
    }
    # print(result)
    return result

#write code to test from cli, i will hardcode csv_path, convert to df, send to find_top_recent_product, print result
if __name__ == "__main__":
    csv_path = "C:/Users/hurai/Downloads/amz.csv"
    df = pd.read_csv(csv_path)
    result = find_top_recent_product(df, "face wash")