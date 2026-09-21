def send_invoice_email_task(*args, **kwargs):
    doc_num = kwargs.get("doc_number", "DOC")
    email = kwargs.get("recipient_email", "N/A")
    print(f"[EMAIL SERVICE BACKGROUND] Successfully processed email dispatch for invoice {doc_num} to {email}")
