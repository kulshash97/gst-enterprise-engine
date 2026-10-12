import os
import hashlib
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory, engine
from app.core.security import generate_tenant_api_key
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.invoice import Invoice, InvoiceItem
from app.api.v1.endpoints import auth, invoices
from app.services.tax_engine import compute_statutory_taxes, HSN_RATES, round_paisa

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup: initialize SQLite/Postgres tables and seed demo tenant
@app.on_event("startup")
async def on_startup():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async with async_session_factory() as session:
            stmt = select(Tenant).where(Tenant.gstin == "36AAFFH9912Q1Z9")
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                raw_key, prefix, hashed = generate_tenant_api_key()
                demo_tenant = Tenant(
                    name="Hitec Cloud Technologies LLP",
                    gstin="36AAFFH9912Q1Z9",
                    state_code="36",
                    key_prefix=prefix,
                    hashed_api_key=hashed,
                    is_active=True
                )
                session.add(demo_tenant)
                await session.commit()
    except Exception as e:
        print(f"Startup notice: {e}")

# Mount API routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Tenant Authentication"])
app.include_router(invoices.router, prefix=f"{settings.API_V1_STR}/invoices", tags=["Statutory Invoicing"])

# Mount static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", tags=["Frontend"])
async def serve_index():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "ApexTax Enterprise Engine API is running. Visit /docs"}

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "HEALTHY", "service": settings.PROJECT_NAME, "env": settings.ENVIRONMENT}

# Backward-compatible UI Invoicing endpoint
@app.post("/create-invoice", tags=["UI Bridge"])
async def ui_create_invoice(request: Request):
    data = await request.json()
    supplier = data.get("supplier", {})
    recipient = data.get("recipient", {})
    doc_number = data.get("doc_number", "INV/2026/001")
    items = data.get("items", [])

    supp_state = str(supplier.get("state_code", "36"))
    rec_state = str(recipient.get("state_code", "36"))
    is_interstate = (supp_state != rec_state)

    total_taxable = Decimal("0.00")
    total_cgst = Decimal("0.00")
    total_sgst = Decimal("0.00")
    total_igst = Decimal("0.00")

    for itm in items:
        qty = Decimal(str(itm.get("quantity", 1)))
        price = Decimal(str(itm.get("unit_price", 0)))
        hsn = str(itm.get("hsn_code", "8471"))[:4]
        rate = HSN_RATES.get(hsn, Decimal("0.18"))
        
        taxable = round_paisa(qty * price)
        tax = compute_statutory_taxes(taxable, rate, is_interstate)

        total_taxable += taxable
        total_cgst += tax["cgst"]
        total_sgst += tax["sgst"]
        total_igst += tax["igst"]

    grand_total = total_taxable + total_cgst + total_sgst + total_igst
    irn_raw = f"{supplier.get('gstin', '36AAFFH9912Q1Z9')}:{doc_number}:2026-27"
    irn = hashlib.sha256(irn_raw.encode()).hexdigest()

    return {
        "status": "SUCCESS",
        "doc_number": doc_number,
        "irn": irn,
        "taxable_value": float(total_taxable),
        "cgst": float(total_cgst),
        "sgst": float(total_sgst),
        "igst": float(total_igst),
        "grand_total": float(grand_total),
        "is_interstate": is_interstate,
        "message": "Statutory IRN generated with paisa-precision math."
    }

# Backward-compatible DRC-01C Generator
@app.post("/generate-drc01c-defense", tags=["UI Bridge"])
async def ui_generate_drc01c(request: Request):
    data = await request.json()
    diff = float(data.get("diff_amount", 145000))
    return {
        "status": "GENERATED",
        "reference_no": "DRC-01C/2026/09/REF-88D",
        "defense_text": (
            f"REPLY TO FORM GST DRC-01C UNDER RULE 88D\n\n"
            f"1. With reference to the intimation of ITC mismatch under Rule 88D for amount INR {diff:,.2f}:\n"
            f"2. The difference represents bona fide inward supplies duly accounted in books with valid tax invoices.\n"
            f"3. Invoices reported by suppliers in subsequent GSTR-1/IFF filings have been reconciled under Section 16(2)(aa).\n"
            f"4. No reversal under Section 50 interest liability is applicable."
        )
    }

# Backward-compatible DRC-01B Generator
@app.post("/generate-drc01b-defense", tags=["UI Bridge"])
async def ui_generate_drc01b(request: Request):
    data = await request.json()
    diff = float(data.get("liability_diff", 220000))
    return {
        "status": "GENERATED",
        "reference_no": "DRC-01B/2026/09/REF-88C",
        "defense_text": (
            f"REPLY TO FORM GST DRC-01B UNDER RULE 88C (CIRCULAR NO. 170/02/2022-GST)\n\n"
            f"1. With reference to outward liability difference of INR {diff:,.2f} between GSTR-1 and GSTR-3B:\n"
            f"2. Typographical error in outward supply reporting in Table 4 of GSTR-1, corrected in subsequent month.\n"
            f"3. In accordance with Circular No. 170, the net tax liability has been fully discharged through electronic cash/credit ledger.\n"
            f"4. Requested not to invoke blocking of GSTR-1 under Rule 59(6)."
        )
    }
