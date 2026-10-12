import hashlib
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.dependencies import get_current_tenant, get_db
from app.models.tenant import Tenant
from app.models.invoice import Invoice, InvoiceItem
from app.schemas.invoice import InvoiceCreateRequest
from app.services.tax_engine import compute_statutory_taxes, HSN_RATES, round_paisa

router = APIRouter()

@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreateRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    # Idempotency check: composite key (tenant_id, doc_number)
    stmt = select(Invoice).where(
        Invoice.tenant_id == current_tenant.id,
        Invoice.doc_number == payload.doc_number
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice {payload.doc_number} already exists for this tenant."
        )

    is_interstate = (current_tenant.state_code != payload.recipient.state_code)
    
    total_taxable = Decimal("0.00")
    total_cgst = Decimal("0.00")
    total_sgst = Decimal("0.00")
    total_igst = Decimal("0.00")

    invoice_items = []
    for item in payload.items:
        hsn_prefix = item.hsn_code[:4]
        tax_rate = HSN_RATES.get(hsn_prefix, Decimal("0.18"))
        item_taxable = round_paisa(item.quantity * item.unit_price)
        taxes = compute_statutory_taxes(item_taxable, tax_rate, is_interstate)

        total_taxable += item_taxable
        total_cgst += taxes["cgst"]
        total_sgst += taxes["sgst"]
        total_igst += taxes["igst"]

        invoice_items.append(
            InvoiceItem(
                item_name=item.item_name,
                hsn_code=item.hsn_code,
                quantity=item.quantity,
                unit_price=item.unit_price,
                taxable_value=item_taxable,
                tax_rate=tax_rate
            )
        )

    grand_total = total_taxable + total_cgst + total_sgst + total_igst

    # Compute mock deterministic IRN hash: SHA256(SupplierGSTIN + DocNo + FY)
    irn_raw = f"{current_tenant.gstin}:{payload.doc_number}:2026-27"
    irn = hashlib.sha256(irn_raw.encode()).hexdigest()

    invoice = Invoice(
        tenant_id=current_tenant.id,
        doc_number=payload.doc_number,
        doc_date=payload.doc_date,
        recipient_name=payload.recipient.legal_name,
        recipient_gstin=payload.recipient.gstin,
        recipient_state=payload.recipient.state_code,
        taxable_value=total_taxable,
        cgst_amount=total_cgst,
        sgst_amount=total_sgst,
        igst_amount=total_igst,
        grand_total=grand_total,
        irn=irn,
        items=invoice_items
    )

    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    return {
        "status": "SUCCESS",
        "invoice_id": invoice.id,
        "doc_number": invoice.doc_number,
        "irn": invoice.irn,
        "taxable_value": float(invoice.taxable_value),
        "cgst": float(invoice.cgst_amount),
        "sgst": float(invoice.sgst_amount),
        "igst": float(invoice.igst_amount),
        "grand_total": float(invoice.grand_total)
    }
