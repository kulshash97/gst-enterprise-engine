import io
import json
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_qr_buffer(qr_data: dict) -> io.BytesIO:
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=1)
    qr.add_data(json.dumps(qr_data, separators=(',', ':')))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def build_gst_tax_invoice_pdf(invoice_data: dict) -> io.BytesIO:
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=28)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=1, textColor=colors.HexColor("#1A202C"))
    subtitle_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=1, textColor=colors.HexColor("#4A5568"))
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor("#2D3748"))
    cell_normal = ParagraphStyle('CellNormal', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor("#2D3748"))
    cell_right = ParagraphStyle('CellRight', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, alignment=2, textColor=colors.HexColor("#2D3748"))

    elements = [
        Paragraph("TAX INVOICE", title_style),
        Paragraph("(Issued under Section 31 of the CGST Act, 2017 read with Rule 46)", subtitle_style),
        Paragraph("<b>ORIGINAL FOR RECIPIENT</b>", subtitle_style),
        Spacer(1, 8)
    ]

    qr_img_buffer = generate_qr_buffer(invoice_data["compliance"]["e_invoice"]["signed_qr_data"])
    qr_image = RLImage(qr_img_buffer, width=1.1*inch, height=1.1*inch)
    irn_string = invoice_data["compliance"]["e_invoice"]["irn"]

    meta_text = f"""
    <b>Invoice No:</b> {invoice_data['doc_number']}<br/>
    <b>Invoice Date:</b> {invoice_data['doc_date']}<br/>
    <b>IRN:</b> <font size="6">{irn_string}</font><br/>
    <b>E-Way Bill Status:</b> {invoice_data['compliance']['e_way_bill']['status']}<br/>
    <b>Vehicle No:</b> {invoice_data['compliance']['e_way_bill']['vehicle_number']}
    """
    header_table = Table([[Paragraph(meta_text, cell_normal), qr_image]], colWidths=[420, 115])
    header_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
    ]))
    elements.extend([header_table, Spacer(1, 6)])

    sup = invoice_data["supplier"]
    rec = invoice_data["recipient"]
    sup_info = f"<b>SUPPLIER DETAILS</b><br/><b>Name:</b> {sup['legal_name']}<br/><b>Address:</b> {sup['address']}, {sup['city']} - {sup['pincode']}<br/><b>GSTIN:</b> {sup['gstin']}"
    rec_info = f"<b>RECIPIENT DETAILS</b><br/><b>Name:</b> {rec['legal_name']}<br/><b>Address:</b> {rec['address']}, {rec['city']} - {rec['pincode']}<br/><b>GSTIN:</b> {rec['gstin']}<br/><b>Place of Supply:</b> {rec['state_code']}"

    party_table = Table([[Paragraph(sup_info, cell_normal), Paragraph(rec_info, cell_normal)]], colWidths=[267, 268])
    party_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E0")),
        ('LINEBEFORE', (1, 0), (1, 0), 0.75, colors.HexColor("#CBD5E0")),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    elements.extend([party_table, Spacer(1, 6)])

    is_inter = invoice_data["tax_summary"]["is_interstate"]
    items_header = [
        Paragraph("#", cell_bold), Paragraph("Description", cell_bold), Paragraph("HSN", cell_bold),
        Paragraph("Qty", cell_bold), Paragraph("Rate (INR)", cell_bold), Paragraph("Taxable (INR)", cell_bold),
        Paragraph("IGST (INR)" if is_inter else "CGST+SGST", cell_bold), Paragraph("Total (INR)", cell_bold)
    ]
    col_widths = [20, 165, 55, 35, 60, 65, 65, 70]
    table_rows = [items_header]

    for idx, item in enumerate(invoice_data.get("line_items", []), 1):
        tax_str = f"{item['igst']:.2f}" if is_inter else f"{(item['cgst'] + item['sgst']):.2f}"
        table_rows.append([
            Paragraph(str(idx), cell_normal),
            Paragraph(item["item_name"], cell_normal),
            Paragraph(item["hsn_code"], cell_normal),
            Paragraph(str(item["quantity"]), cell_normal),
            Paragraph(f"{item['unit_price']:.2f}", cell_right),
            Paragraph(f"{item['taxable_value']:.2f}", cell_right),
            Paragraph(tax_str, cell_right),
            Paragraph(f"{item['line_total']:.2f}", cell_right),
        ])

    tax_sum = invoice_data["tax_summary"]
    tot_tax = tax_sum['igst'] if is_inter else (tax_sum['cgst'] + tax_sum['sgst'])
    table_rows.append([
        Paragraph("<b>Total</b>", cell_bold), "", "", "", "",
        Paragraph(f"<b>Rs. {tax_sum['total_taxable_value']:.2f}</b>", cell_right),
        Paragraph(f"<b>Rs. {tot_tax:.2f}</b>", cell_right),
        Paragraph(f"<b>Rs. {tax_sum['grand_total']:.2f}</b>", cell_right),
    ])

    items_table = Table(table_rows, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#F7FAFC")),
        ('SPAN', (0, -1), (4, -1)),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.extend([items_table, Spacer(1, 10)])

    footer_text = "<b>Statutory Declaration:</b><br/>This is an authenticated computer-generated invoice under NIC e-Invoice system and Rule 46 of CGST Rules, 2017."
    auth_box = f"For <b>{sup['legal_name']}</b><br/><br/><br/><b>Authorized Signatory</b>"
    footer_table = Table([[Paragraph(footer_text, cell_normal), Paragraph(auth_box, ParagraphStyle('AR', parent=cell_bold, alignment=1))]], colWidths=[370, 165])
    footer_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E0")),
        ('LINEBEFORE', (1, 0), (1, 0), 0.75, colors.HexColor("#CBD5E0")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(KeepTogether(footer_table))

    doc.build(elements)
    pdf_buffer.seek(0)
    return pdf_buffer
