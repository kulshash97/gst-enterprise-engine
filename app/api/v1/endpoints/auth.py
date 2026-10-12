from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.api.dependencies import get_db
from app.core.security import generate_tenant_api_key
from app.models.tenant import Tenant

router = APIRouter()

class TenantRegisterRequest(BaseModel):
    name: str
    gstin: str
    state_code: str

class TenantRegisterResponse(BaseModel):
    tenant_id: int
    name: str
    gstin: str
    key_prefix: str
    api_key: str
    message: str

@router.post("/register", response_model=TenantRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_tenant(req: TenantRegisterRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(Tenant).where(Tenant.gstin == req.gstin)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant with this GSTIN already registered.")

    raw_key, prefix, hashed_key = generate_tenant_api_key()
    tenant = Tenant(
        name=req.name,
        gstin=req.gstin,
        state_code=req.state_code,
        key_prefix=prefix,
        hashed_api_key=hashed_key,
        is_active=True
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return TenantRegisterResponse(
        tenant_id=tenant.id,
        name=tenant.name,
        gstin=tenant.gstin,
        key_prefix=prefix,
        api_key=raw_key,
        message="Store this API key securely. It cannot be recovered."
    )
