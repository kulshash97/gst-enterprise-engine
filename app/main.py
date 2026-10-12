from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.v1.endpoints import auth, invoices

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire modular enterprise routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Tenant Authentication"])
app.include_router(invoices.router, prefix=f"{settings.API_V1_STR}/invoices", tags=["Statutory Invoicing"])

# Mount static frontend
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "HEALTHY", "service": settings.PROJECT_NAME, "env": settings.ENVIRONMENT}
