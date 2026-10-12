from typing import AsyncGenerator
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import verify_api_key
from app.models.tenant import Tenant

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def get_current_tenant(
    x_api_key: str = Header(..., alias="X-API-Key", description="Tenant API Secret Key"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    if not x_api_key.startswith("apex_") or "_" not in x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed or missing API Key structure.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    parts = x_api_key.split("_")
    if len(parts) < 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key format.")
    prefix = f"{parts[0]}_{parts[1]}"

    stmt = select(Tenant).where(Tenant.key_prefix == prefix, Tenant.is_active == True)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()

    if not tenant or not verify_api_key(x_api_key, tenant.hashed_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return tenant
