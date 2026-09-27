"""
FR-28: Export to Word/PDF with correct formatting preserved.
"""
import os
from docx import Document
from docx.shared import Pt
from fpdf import FPDF

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)


def export_text_docx(title, body_text, filename):
    doc = Document()
    heading = doc.add_heading(title, level=1)
    for para in body_text.split("\n\n"):
        p = doc.add_paragraph(para.strip())
        p.style.font.size = Pt(11)
    path = os.path.join(EXPORT_DIR, filename)
    doc.save(path)
    return path


def export_text_pdf(title, body_text, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 10, title)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)
    for para in body_text.split("\n"):
        pdf.multi_cell(0, 7, para)
    path = os.path.join(EXPORT_DIR, filename)
    pdf.output(path)
    return path


def export_invoice_docx(invoice, client, firm_name, filename):
    doc = Document()
    doc.add_heading(firm_name, level=1)
    doc.add_paragraph(
        "Tax Invoice" if invoice.invoice_type == "invoice"
        else invoice.invoice_type.replace("_", " ").title()
    )
    doc.add_paragraph(f"Invoice No: {invoice.invoice_number}")
    doc.add_paragraph(f"Date: {invoice.created_at.strftime('%d-%b-%Y')}")
    if invoice.reference_invoice:
        doc.add_paragraph(f"Reference Invoice: {invoice.reference_invoice}")
    doc.add_paragraph(f"Place of Supply: {invoice.place_of_supply or '-'}")

    doc.add_heading("Bill To", level=2)
    doc.add_paragraph(client.name)
    doc.add_paragraph(f"GSTIN: {client.gstin or '-'}")
    doc.add_paragraph(f"PAN: {client.pan or '-'}")
    doc.add_paragraph(client.address or "")

    doc.add_heading("Particulars", level=2)
    table = doc.add_table(rows=1, cols=2)
    hdr = table.rows[0].cells
    hdr[0].text = "Description"
    hdr[1].text = "Amount (INR)"
    row = table.add_row().cells
    row[0].text = f"{invoice.service_description}\nHSN/SAC: {invoice.hsn_sac}"
    row[1].text = f"{invoice.fee_amount:,.2f}"
    if invoice.reimbursement:
        row2 = table.add_row().cells
        row2[0].text = "Reimbursement of Expenses"
        row2[1].text = f"{invoice.reimbursement:,.2f}"

    doc.add_paragraph(f"Taxable Value: {invoice.taxable_value:,.2f}")
    doc.add_paragraph(f"GST @ {invoice.gst_rate}%: {invoice.tax_amount:,.2f}")
    if invoice.tds_applicable:
        doc.add_paragraph(f"(TDS @ {invoice.tds_rate}% deductible by client at source)")
    doc.add_paragraph(f"Total Amount: {invoice.currency} {invoice.total_amount:,.2f}").bold = True
    doc.add_paragraph(f"Amount in Words: {invoice.amount_in_words}")

    path = os.path.join(EXPORT_DIR, filename)
    doc.save(path)
    return path


def export_invoice_pdf(invoice, client, firm_name, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, firm_name, ln=True)
    pdf.set_font("Helvetica", "", 11)
    label = "TAX INVOICE" if invoice.invoice_type == "invoice" else invoice.invoice_type.upper()
    pdf.cell(0, 8, label, ln=True)
    pdf.ln(2)
    pdf.cell(0, 7, f"Invoice No: {invoice.invoice_number}", ln=True)
    pdf.cell(0, 7, f"Date: {invoice.created_at.strftime('%d-%b-%Y')}", ln=True)
    if invoice.reference_invoice:
        pdf.cell(0, 7, f"Reference Invoice: {invoice.reference_invoice}", ln=True)
    pdf.cell(0, 7, f"Place of Supply: {invoice.place_of_supply or '-'}", ln=True)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Bill To:", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, client.name, ln=True)
    pdf.cell(0, 7, f"GSTIN: {client.gstin or '-'}   PAN: {client.pan or '-'}", ln=True)
    pdf.multi_cell(0, 7, client.address or "")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(130, 8, "Description", border=1)
    pdf.cell(0, 8, "Amount (INR)", border=1, ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(130, 8, f"{invoice.service_description}\nHSN/SAC: {invoice.hsn_sac}", border=1)
    pdf.set_xy(140, pdf.get_y() - 16 if pdf.get_y() > 16 else pdf.get_y())

    pdf.ln(3)
    pdf.cell(0, 7, f"Taxable Value: {invoice.taxable_value:,.2f}", ln=True)
    pdf.cell(0, 7, f"GST @ {invoice.gst_rate}%: {invoice.tax_amount:,.2f}", ln=True)
    if invoice.reimbursement:
        pdf.cell(0, 7, f"Reimbursement: {invoice.reimbursement:,.2f}", ln=True)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Total Amount: {invoice.currency} {invoice.total_amount:,.2f}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, f"Amount in Words: {invoice.amount_in_words}")

    path = os.path.join(EXPORT_DIR, filename)
    pdf.output(path)
    return path
