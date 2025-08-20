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

def filter_csv_by_reviews_and_keyword(input_csv, keyword_phrase, max_reviews=1000):
    """
    Filters input CSV rows where:
      - Review Count <= max_reviews i.e. 1000
      - Display Order column includes the keyword_phrase (case-insensitive)

    Saves filtered rows to output_csv.
    """
    filtered_rows = []
    # print(keyword_phrase.lower())

    # Open and read input CSV
    with open(input_csv, newline='', encoding='utf-8-sig') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        for row in reader:
            # Parse Review Count as integer, handle commas
            try:
                review_count = int(str(row.get('Review Count', '0')).replace(',', '').strip())
            except ValueError:
                review_count = 0

            display_order = str(row.get('Product Details', '')).lower()
            keyword_lower = keyword_phrase.lower()

            # print(review_count,display_order)
            if review_count <= max_reviews and keyword_lower in display_order:
                # print(review_count, display_order)
                filtered_rows.append(row)

    # print(input_csv)
    output_csv = os.path.join(os.getcwd(), "exports", f"filtered_{os.path.basename(input_csv)}")
    # Write filtered rows to output CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_rows)

    print(f"[SUCCESS] Filtered CSV saved to {output_csv} ({len(filtered_rows)} rows).")
    return output_csv

def filter_next_product(downloaded_path: str, title_keyword: str):
    """
    Select the most recent product by:
      1) Filtering rows whose 'Product Details' contains title_keyword
         (case-insensitive, supports partial phrases)
      2) Sorting by 'Creation Date' (descending)
      3) Returning the single most recent row as dict

    Returns:
        dict: the most recent product row

    Raises:
        ValueError: if required columns are missing or no matching rows exist
    """
    # Read CSV
    df = pd.read_csv(downloaded_path)

    # Required columns
    required_cols = ["Product Details", "Creation Date"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Filter by keyword (word or phrase, partial match, case-insensitive)
    filtered = df[df["Product Details"]
                  .astype(str)
                  .str.contains(title_keyword, case=False, na=False, regex=False)]
    if filtered.empty:
        raise ValueError("No products matched the keyword in 'Product Details'.")

    # Parse Creation Date
    filtered["__creation_dt"] = pd.to_datetime(filtered["Creation Date"], errors="coerce")
    filtered = filtered.dropna(subset=["__creation_dt"])
    if filtered.empty:
        raise ValueError("No products have a valid 'Creation Date' after filtering by keyword.")

    # Pick the most recent product
    selected = filtered.sort_values("__creation_dt", ascending=False).iloc[0]

    # Return dict without helper column
    return selected.drop(labels=[c for c in selected.index if c.startswith("")], errors="ignore").to_dict()


def find_top_recent_product(csv_path: str, keyword_phrase: str, within_years: int = 2) -> Optional[Dict[str, str]]:
    """
    Scan the CSV and return a dict with the best recent product:
    - Max 'Parent Level Revenue'
    - 'Creation Date' within last `within_years` years (approx. 365*years days)

    Returns None if no qualifying rows found.
    """
    csv_path = filter_csv_by_reviews_and_keyword(csv_path, keyword_phrase)
    cutoff = datetime.now() - timedelta(days=365 * within_years)
    best_row = None
    best_rev = float("-inf")

    # utf-8-sig handles BOM if present
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # Normalize headers by stripping whitespace
        reader.fieldnames = [h.strip() for h in reader.fieldnames] if reader.fieldnames else None

        for row in reader:
            # Access columns defensively
            created_at = _parse_date(row.get(COL_CREATION_DATE))
            if not created_at or created_at < cutoff:
                continue

            rev = _to_number(row.get(COL_PARENT_REVENUE))
            if rev is None:
                continue

            if rev > best_rev:
                best_rev = rev
                best_row = row
            elif rev == best_rev and best_row:
                # Tie-breaker 1: most recent Creation Date wins
                prev_dt = _parse_date(best_row.get(COL_CREATION_DATE))
                if prev_dt and created_at > prev_dt:
                    best_row = row
                # (Optional) add more tie-breakers if you like (e.g., higher Review Count)

    if not best_row:
        return None

    # Build a concise result payload (add fields as you need)
    result = {
        "product_details": (best_row.get(COL_PRODUCT_DETAILS) or "").strip(),
        "url": (best_row.get(COL_URL) or "").strip(),
        "parent_level_revenue": str(best_row.get(COL_PARENT_REVENUE) or "").strip(),
        "creation_date": str(best_row.get(COL_CREATION_DATE) or "").strip(),
        # Handy extras you might want downstream
        "asin": (best_row.get("ASIN") or "").strip(),
        "brand": (best_row.get("Brand") or "").strip(),
        "price": (best_row.get("Price  $") or "").strip(),
    }
    return result

# Optional: quick CLI test
if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python csv_picker.py <path_to_csv>")
        sys.exit(1)
    res = find_top_recent_product(sys.argv[1])
    print(json.dumps(res, indent=2) if res else "No qualifying product found.")
