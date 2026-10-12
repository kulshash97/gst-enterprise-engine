from decimal import Decimal, ROUND_HALF_UP

PAISA = Decimal("0.01")

HSN_RATES = {
    "8471": Decimal("0.18"),
    "8517": Decimal("0.18"),
    "6109": Decimal("0.05"),
    "1006": Decimal("0.00"),
    "9983": Decimal("0.18"),
    "8703": Decimal("0.28"),
}

def round_paisa(val: Decimal) -> Decimal:
    return val.quantize(PAISA, rounding=ROUND_HALF_UP)

def compute_statutory_taxes(taxable_value: Decimal, hsn_rate: Decimal, is_interstate: bool) -> dict:
    taxable_value = round_paisa(taxable_value)
    total_tax = round_paisa(taxable_value * hsn_rate)

    if is_interstate:
        return {
            "taxable_value": taxable_value,
            "cgst": Decimal("0.00"),
            "sgst": Decimal("0.00"),
            "igst": total_tax,
            "grand_total": taxable_value + total_tax
        }
    else:
        cgst = round_paisa(total_tax / Decimal("2"))
        sgst = total_tax - cgst
        return {
            "taxable_value": taxable_value,
            "cgst": cgst,
            "sgst": sgst,
            "igst": Decimal("0.00"),
            "grand_total": taxable_value + total_tax
        }
