import re
from typing import List, Dict, Any

def normalize_doc_num(doc_no: str) -> str:
    """Normalize invoice numbers to prevent false mismatches caused by slashes/hyphens/spaces."""
    if not doc_no:
        return ""
    return re.sub(r'[^A-Za-z0-9]', '', str(doc_no)).upper()

def run_gstr2b_reconciliation(purchase_register: List[Dict[str, Any]], gstr2b_b2b_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    matched = []
    missing_in_2b = []
    mismatched = []
    
    # Track used 2B records to find orphan 2B invoices
    used_2b_keys = set()

    # Build lookup index for 2B: key = (Vendor GSTIN, normalized_doc_num)
    lookup_2b = {}
    for idx, rec in enumerate(gstr2b_b2b_records):
        ctin = rec.get("ctin", "").strip().upper()
        doc_no = normalize_doc_num(rec.get("inum", ""))
        lookup_2b[(ctin, doc_no)] = (idx, rec)

    # Reconcile Purchase Register against 2B
    for pr in purchase_register:
        pr_ctin = pr.get("vendor_gstin", "").strip().upper()
        pr_doc_raw = pr.get("doc_number", "")
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

            if val_diff <= 1.0 and tax_diff <= 1.0:
                matched.append({
                    "vendor_gstin": pr_ctin,
                    "vendor_name": pr.get("vendor_name", b2b.get("trade_name", "Vendor")),
                    "doc_number": pr_doc_raw,
                    "doc_date": pr.get("doc_date", b2b.get("dt", "")),
                    "taxable_value": pr_val,
                    "itc_claimed": pr_tax,
                    "status": "MATCHED_ELIGIBLE",
                    "remarks": "Eligible under Sec 16(2)(aa)"
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
                    "action": "Withhold tax difference pending vendor debit/credit note"
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
                "action": "Vendor defaulted on GSTR-1. Hold payment until filed."
            })

    # Unrecorded in books
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

    total_eligible_itc = sum(item["itc_claimed"] for item in matched)
    total_at_risk_itc = sum(item["itc_at_risk"] for item in missing_in_2b)

    return {
        "summary": {
            "total_purchases_reviewed": len(purchase_register),
            "matched_count": len(matched),
            "missing_in_2b_count": len(missing_in_2b),
            "mismatch_count": len(mismatched),
            "in_2b_not_in_books_count": len(in_2b_not_in_books),
            "total_eligible_itc": round(total_eligible_itc, 2),
            "total_at_risk_itc": round(total_at_risk_itc, 2),
        },
        "matched": matched,
        "missing_in_2b": missing_in_2b,
        "mismatched": mismatched,
        "in_2b_not_in_books": in_2b_not_in_books
    }
