from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    org_name = Column(String(100), nullable=False)
    api_key = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    invoices = relationship("Invoice", back_populates="tenant")

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    doc_number = Column(String(50), nullable=False)
    doc_date = Column(String(10), nullable=False)
    supplier_legal_name = Column(String(150), nullable=False)
    supplier_gstin = Column(String(15), nullable=False)
    supplier_state_code = Column(String(2), nullable=False)
    buyer_legal_name = Column(String(150), nullable=False)
    buyer_gstin = Column(String(15), nullable=False)
    buyer_state_code = Column(String(2), nullable=False)
    total_taxable_value = Column(Float, nullable=False)
    cgst_amount = Column(Float, default=0.0)
    sgst_amount = Column(Float, default=0.0)
    igst_amount = Column(Float, default=0.0)
    grand_total = Column(Float, nullable=False)
    irn = Column(String(64), unique=True, index=True, nullable=True)
    eway_bill_required = Column(Boolean, default=False)
    eway_bill_status = Column(String(30), default="NOT_APPLICABLE")
    vehicle_number = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    tenant = relationship("Tenant", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice")

class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), index=True, nullable=False)
    item_name = Column(String(150), nullable=False)
    hsn_code = Column(String(8), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    taxable_value = Column(Float, nullable=False)
    tax_rate = Column(Float, nullable=False)
    invoice = relationship("Invoice", back_populates="items")

class ComplianceAuditLog(Base):
    __tablename__ = "compliance_audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    event_type = Column(String(50), nullable=False)
    doc_number = Column(String(50), nullable=False)
    details = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
