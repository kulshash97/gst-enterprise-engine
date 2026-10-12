from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"

def test_protected_invoice_endpoint_rejects_missing_key():
    payload = {
        "doc_number": "INV/TEST/001",
        "doc_date": "2026-10-12",
        "recipient": {
            "legal_name": "Test Recipient",
            "gstin": "29AABCU9603R1ZX",
            "address": "Bangalore",
            "city": "Bangalore",
            "state_code": "29",
            "pincode": 560001
        },
        "items": [
            {
                "item_name": "Test Item",
                "hsn_code": "84713010",
                "quantity": 1,
                "unit_price": 50000
            }
        ]
    }
    # Request without X-API-Key header
    response = client.post("/api/v1/invoices/create", json=payload)
    assert response.status_code == 422 or response.status_code == 401
