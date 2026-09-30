import re
import json
import io
import pandas as pd
from typing import List, Dict, Any, Tuple

def normalize_doc_num(doc_no: Any) -> str:
    """Strip special characters, spaces, and leading zeros to eliminate false mismatch flags."""
    if doc_no is None:
        return ""
    cleaned = re.sub(r'[^A-Za-z0-9]', '', str(doc_no)).upper()
    return cleaned.lstrip('0')

def find_column(df_columns: List[str], candidate_names: List[str]) -> str:
    """Fuzzy-match client column headers against expected concepts."""
    cleaned_candidates = [c.lower().replace(" ", "").replace("_", "") for c in candidate_names]
    for col in df_columns:
        normalized_col = str(col).lower().replace(" ", "").replace("_", "").replace(".", "")
        for cand in cleaned_candidates:
            if cand in normalized_col:
                return col
    return ""

def parse_purchase_register_file(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """Parse Excel (.xlsx, .xls) or CSV purchase registers into a normalized schema."""
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes))
    else:
        df = pd.read_excel(io.BytesIO(file_bytes))

    df = df.dropna(how="all")
    cols = list(df.columns)

    gstin_col = find_column(cols, ["gstin", "vendor_gst", "supplier_gst", "ctin", "gst"])
    name_col = find_column(cols, ["vendor", "supplier", "party", "name", "trade"])
    inv_col = find_column(cols, ["invoice", "inv_no", "bill_no", "doc_no", "number", "inum"])
    date_col = find_column(cols, ["date", "inv_date", "bill_date", "dt"])
    taxable_col = find_column(cols, ["taxable", "taxable_val", "assessable", "base_val", "txval"])
    tax_col = find_column(cols, ["tax", "total_tax", "gst_amount", "igst", "tax_amt"])

    records = []
    for _, row in df.iterrows():
        gstin_val = str(row[gstin_col]).strip().upper() if gstin_col and pd.notna(row[gstin_col]) else "UNKNOWN_GSTIN"
        name_val = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else "Vendor"
        inv_val = str(row[inv_col]).strip() if inv_col and pd.notna(row[inv_col]) else ""
        date_val = str(row[date_col]).strip() if date_col and pd.notna(row[date_col]) else ""
        
        try:
            taxable_val = round(float(row[taxable_col]), 2) if taxable_col and pd.notna(row[taxable_col]) else 0.0
        except (ValueError, TypeError):
            taxable_val = 0.0

        try:
            tax_val = round(float(row[tax_col]), 2) if tax_col and pd.notna(row[tax_col]) else 0.0
        except (ValueError, TypeError):
            tax_val = 0.0

        if inv_val:
            records.append({
                "vendor_gstin": gstin_val,
                "vendor_name": name_val,
                "doc_number": inv_val,
                "doc_date": date_val,
                "taxable_value": taxable_val,
                "tax_amount": tax_val
            })
    return records

def parse_gstr2b_json_file(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse official GSTR-2B JSON hierarchy (data -> docdata -> b2b -> inv)."""
    raw_data = json.loads(file_bytes.decode("utf-8"))
    b2b_records = []

    # Handle standard GST portal JSON wrapper
    data_block = raw_data.get("data", raw_data)
    doc_data = data_block.get("docdata", data_block)
    b2b_list = doc_data.get("b2b", [])

    for vendor in b2b_list:
        ctin = vendor.get("ctin", "").strip().upper()
        trade_name = vendor.get("trdnm", vendor.get("trade_name", "Supplier"))
        inv_list = vendor.get("inv", [])

        for inv in inv_list:
            inum = str(inv.get("inum", "")).strip()
            dt = str(inv.get("dt", "")).strip()
            val = float(inv.get("val", 0.0))
            
            # Sum line item values
            items = inv.get("items", [])
            tot_txval = 0.0
            tot_iamt = 0.0
            tot_camt = 0.0
            tot_samt = 0.0

            for itm in items:
                itm_det = itm.get("item_det", itm)
                tot_txval += float(itm_det.get("txval", 0.0))
                tot_iamt += float(itm_det.get("iamt", 0.0))
                tot_camt += float(itm_det.get("camt", 0.0))
                tot_samt += float(itm_det.get("samt", 0.0))

            if tot_txval == 0.0 and val > 0.0:
                tot_txval = val

            b2b_records.append({
                "ctin": ctin,
                "trade_name": trade_name,
                "inum": inum,
                "dt": dt,
                "txval": round(tot_txval, 2),
                "iamt": round(tot_iamt, 2),
                "camt": round(tot_camt, 2),
                "samt": round(tot_samt, 2)
            })

    return b2b_records

def run_gstr2b_reconciliation(purchase_register: List[Dict[str, Any]], gstr2b_b2b_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    matched = []
    missing_in_2b = []
    mismatched = []
    used_2b_keys = set()

    # Index 2B records by (CTIN, normalized_doc)
    lookup_2b = {}
    for idx, rec in enumerate(gstr2b_b2b_records):
        ctin = rec.get("ctin", "").strip().upper()
        doc_no = normalize_doc_num(rec.get("inum", ""))
        lookup_2b[(ctin, doc_no)] = (idx, rec)

    for pr in purchase_register:
        pr_ctin = pr.get("vendor_gstin", "").strip().upper()
        pr_doc_raw = str(pr.get("doc_number", ""))
        pr_doc = normalize_doc_num(pr_doc_raw)
        pr_val = round(float(pr.get("taxable_value", 0.0)), 2)
        pr_tax = round(float(pr.get("tax_amount", 0.0)), 2)

        key = (pr_ctin, pr_doc)
        if key in lookup_2b:
            idx, b2b = lookup_2b[key]
            used_2b_keys.add(idx)
            b2b_val = round(float(b2b.get("txval", 0.0)), 2)
            b2b_tax = round(float(b2b.get("iamt", 0.0) + b2b.get("camt", 0.0) + b2b.get("samt", 0.0)), 2)

            val_diff = abs(pr_val - b2b_val)
            tax_diff = abs(pr_tax - b2b_tax)

            if val_diff <= 1.5 and (tax_diff <= 1.5 or pr_tax == 0.0):
                matched.append({
                    "vendor_gstin": pr_ctin,
                    "vendor_name": pr.get("vendor_name", b2b.get("trade_name", "Vendor")),
                    "doc_number": pr_doc_raw,
                    "doc_date": pr.get("doc_date", b2b.get("dt", "")),
                    "taxable_value": pr_val,
                    "itc_claimed": b2b_tax if pr_tax == 0.0 else pr_tax,
                    "status": "MATCHED_ELIGIBLE",
                    "remarks": "100% Eligible under Sec 16(2)(aa)"
                })
            else:
                mismatched.append({
                    "vendor_gstin": pr_ctin,
                    "vendor_name": pr.get("vendor_name", "Vendor"),
                    "doc_number": pr_doc_raw,
                    "books_taxable": pr_val,
                    "portal_taxable": b2b_val,
                    "books_tax": pr_tax,
                    "portal_tax": b2b_tax,
                    "tax_diff": round(pr_tax - b2b_tax, 2),
                    "status": "MISMATCH_DISCREPANCY",
                    "action": "Withhold tax difference pending vendor credit/debit note"
                })
        else:
            missing_in_2b.append({
                "vendor_gstin": pr_ctin,
                "vendor_name": pr.get("vendor_name", "Unknown Vendor"),
                "doc_number": pr_doc_raw,
                "doc_date": pr.get("doc_date", ""),
                "taxable_value": pr_val,
                "itc_at_risk": pr_tax,
                "status": "MISSING_IN_GSTR2B",
                "action": "Vendor defaulted on GSTR-1. HOLD payment until filed."
            })

    in_2b_not_in_books = []
    for idx, rec in enumerate(gstr2b_b2b_records):
        if idx not in used_2b_keys:
            in_2b_not_in_books.append({
                "vendor_gstin": rec.get("ctin"),
                "vendor_name": rec.get("trade_name", "Vendor"),
                "doc_number": rec.get("inum"),
                "doc_date": rec.get("dt"),
                "taxable_value": rec.get("txval"),
                "itc_available": round(float(rec.get("iamt", 0.0) + rec.get("camt", 0.0) + rec.get("samt", 0.0)), 2),
                "status": "PENDING_BOOK_ENTRY"
            })

    total_eligible = sum(item["itc_claimed"] for item in matched)
    total_at_risk = sum(item["itc_at_risk"] for item in missing_in_2b)

    return {
        "summary": {
            "total_purchases_reviewed": len(purchase_register),
            "matched_count": len(matched),
            "missing_in_2b_count": len(missing_in_2b),
            "mismatch_count": len(mismatched),
            "in_2b_not_in_books_count": len(in_2b_not_in_books),
            "total_eligible_itc": round(total_eligible, 2),
            "total_at_risk_itc": round(total_at_risk, 2)
        },
        "matched": matched,
        "missing_in_2b": missing_in_2b,
        "mismatched": mismatched,
        "in_2b_not_in_books": in_2b_not_in_books
    }
