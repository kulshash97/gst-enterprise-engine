import re
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import List, Optional
from datetime import date

GSTIN_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"

class PartySchema(BaseModel):
    legal_name: str = Field(..., max_length=150)
    gstin: str = Field(..., max_length=15)
    address: str = Field(..., max_length=200)
    city: str = Field(..., max_length=50)
    state_code: str = Field(..., min_length=2, max_length=2)
    pincode: int = Field(..., ge=100000, le=999999)
    email: Optional[EmailStr] = None

    @field_validator("gstin")
    @classmethod
    def validate_gstin_format(cls, v):
        v = v.strip().upper()
        if not re.match(GSTIN_REGEX, v):
            raise ValueError(f"Invalid GSTIN format: {v}")
        return v

class ItemSchema(BaseModel):
    item_name: str = Field(..., max_length=100)
    hsn_code: str = Field(..., min_length=4, max_length=8)
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    unit: str = "NOS"

class CreateInvoiceRequest(BaseModel):
    doc_number: str = Field(..., max_length=50)
    doc_date: date
    supplier: PartySchema
    recipient: PartySchema
    items: List[ItemSchema] = Field(..., min_length=1)
    vehicle_number: Optional[str] = None
