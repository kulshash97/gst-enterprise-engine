HSN_TAX_SLABS = {
    "8471": 0.18,
    "8517": 0.18,
    "6109": 0.05,
    "1006": 0.00,
    "9983": 0.18,
    "8703": 0.28,
}

def compute_gst_split(supplier_gstin: str, recipient_gstin: str, items: list):
    supplier_state = supplier_gstin[:2]
    recipient_state = recipient_gstin[:2]
    is_interstate = (supplier_state != recipient_state)

    line_items_calculated = []
    total_taxable_value = 0.0
    total_cgst = 0.0
    total_sgst = 0.0
    total_igst = 0.0

    for item in items:
        taxable_amt = round(item.quantity * item.unit_price, 2)
        total_taxable_value += taxable_amt

        hsn_prefix = item.hsn_code[:4]
        gst_rate = HSN_TAX_SLABS.get(hsn_prefix, 0.18)
        tax_amt = round(taxable_amt * gst_rate, 2)

        if is_interstate:
            cgst = 0.0
            sgst = 0.0
            igst = tax_amt
        else:
            cgst = round(tax_amt / 2.0, 2)
            sgst = round(tax_amt / 2.0, 2)
            igst = 0.0

        total_cgst += cgst
        total_sgst += sgst
        total_igst += igst

        line_items_calculated.append({
            "item_name": item.item_name,
            "hsn_code": item.hsn_code,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "taxable_value": taxable_amt,
            "tax_rate": gst_rate * 100,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "line_total": round(taxable_amt + cgst + sgst + igst, 2)
        })

    grand_total = round(total_taxable_value + total_cgst + total_sgst + total_igst, 2)
    return {
        "is_interstate": is_interstate,
        "total_taxable_value": round(total_taxable_value, 2),
        "total_cgst": round(total_cgst, 2),
        "total_sgst": round(total_sgst, 2),
        "total_igst": round(total_igst, 2),
        "grand_total": grand_total,
        "line_items": line_items_calculated
    }
