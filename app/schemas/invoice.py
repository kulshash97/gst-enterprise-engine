from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field

class LineItemSchema(BaseModel):
    item_name: str
    hsn_code: str = Field(..., min_length=4, max_length=8)
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0)

class RecipientSchema(BaseModel):
    legal_name: str
    gstin: str = Field(..., min_length=15, max_length=15)
    address: str
    city: str
    state_code: str = Field(..., min_length=2, max_length=2)
    pincode: int
    email: Optional[str] = None

class InvoiceCreateRequest(BaseModel):
    doc_number: str
    doc_date: date
    recipient: RecipientSchema
    items: List[LineItemSchema]
    vehicle_number: Optional[str] = None
