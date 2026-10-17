from decimal import Decimal
from typing import List
from pydantic import BaseModel, Field, model_validator

class ExtractedLineItem(BaseModel):
    description: str
    hsn_code: str
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0)
    taxable_value: Decimal = Field(..., ge=0)

class ExtractedInvoiceDossier(BaseModel):
    invoice_number: str
    invoice_date: str
    supplier_gstin: str = Field(..., min_length=15, max_length=15)
    recipient_gstin: str = Field(..., min_length=15, max_length=15)
    taxable_total: Decimal
    total_tax_amount: Decimal
    grand_total: Decimal
    items: List[ExtractedLineItem]

    @model_validator(mode="after")
    def verify_financial_invariants(self) -> "ExtractedInvoiceDossier":
        calculated_taxable = sum(i.quantity * i.unit_price for i in self.items)
        if abs(calculated_taxable - self.taxable_total) > Decimal("0.05"):
            raise ValueError(
                f"Financial Invariant Drift: Line item sum ({calculated_taxable}) "
                f"does not match document total ({self.taxable_total})"
            )
        return self
