# ApexTax Enterprise | Autonomous GST & Statutory Audit Engine

A high-throughput, multi-tenant compliance and reconciliation engine designed for Indian enterprises and tax practitioners. Built with FastAPI, PostgreSQL, and Celery, ApexTax automates statutory tax distribution, NIC-compliant e-invoicing, GSTR-2B Input Tax Credit (ITC) audits under Section 16(2)(aa), and Rule 88D/88C defense filings.

---

## 🏗️ Architecture Overview

The system follows a modular hexagonal architecture separating statutory rule engines from web protocols and worker queues:

```text
[Client / UI / Webhooks]
           │
           ▼
[FastAPI Gateway] ──(Header-Based Auth)──► [Argon2id Tenant Verification]
     │          │
     │          └─► [PostgreSQL 16] (ACID, Numeric(14,2) Paisa Precision)
     │
     ▼ (Asynchronous Task Delegation)
 [Redis Broker]
     │
     ▼
[Celery Workers] ──► Vectorized GSTR-2B Matching & Large PDF Generation
