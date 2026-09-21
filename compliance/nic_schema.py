import hashlib
from datetime import date

def build_nic_standard_payload(supplier, recipient, tax_data, doc_number: str, doc_date: date):
    fin_year = f"{doc_date.year}-{str(doc_date.year + 1)[-2:]}"
    raw_irn_seed = f"{supplier.gstin}:{fin_year}:INV:{doc_number}"
    irn = hashlib.sha256(raw_irn_seed.encode("utf-8")).hexdigest()

    nic_payload = {
        "Version": "1.03",
        "DocDtls": {"Typ": "INV", "No": doc_number, "Dt": str(doc_date)},
        "SellerDtls": {"Gstin": supplier.gstin, "LglNm": supplier.legal_name},
        "BuyerDtls": {"Gstin": recipient.gstin, "LglNm": recipient.legal_name},
        "ValDtls": {"TotInvVal": tax_data["grand_total"]}
    }

    qr_payload = {
        "IRN": irn,
        "Seller": supplier.gstin,
        "Buyer": recipient.gstin,
        "DocNo": doc_number,
        "Total": tax_data["grand_total"]
    }
    return irn, nic_payload, qr_payload
