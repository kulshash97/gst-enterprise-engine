from decimal import Decimal
import pytest
from app.services.tax_engine import compute_statutory_taxes

def test_intrastate_tax_split_precision():
    taxable_value = Decimal("10000.50")
    hsn_rate = Decimal("0.18")
    is_interstate = False

    result = compute_statutory_taxes(taxable_value, hsn_rate, is_interstate)

    assert result["taxable_value"] == Decimal("10000.50")
    assert result["cgst"] == Decimal("900.05")
    assert result["sgst"] == Decimal("900.04")
    assert result["igst"] == Decimal("0.00")
    assert result["grand_total"] == Decimal("11800.59")

def test_interstate_tax_allocation():
    taxable_value = Decimal("55250.75")
    hsn_rate = Decimal("0.18")
    is_interstate = True

    result = compute_statutory_taxes(taxable_value, hsn_rate, is_interstate)

    assert result["taxable_value"] == Decimal("55250.75")
    assert result["cgst"] == Decimal("0.00")
    assert result["sgst"] == Decimal("0.00")
    assert result["igst"] == Decimal("9945.14")
    assert result["grand_total"] == Decimal("65195.89")
