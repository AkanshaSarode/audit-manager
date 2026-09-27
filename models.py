from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# ---------------------------------------------------------------------
# FR-25/27: Users & Roles (Executive, Manager, Admin)
# ---------------------------------------------------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="executive")
    # roles: executive | manager | admin
    designation = db.Column(db.String(120), default="Audit Executive")
    firm_name = db.Column(db.String(200), default="Your CA Firm")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------
# Client Master Data
# ---------------------------------------------------------------------
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    gstin = db.Column(db.String(20))
    pan = db.Column(db.String(20))
    address = db.Column(db.String(300))
    contact_person = db.Column(db.String(120))
    contact_email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    engagements = db.relationship("Engagement", backref="client", lazy=True)


# ---------------------------------------------------------------------
# Engagement Data
# ---------------------------------------------------------------------
class Engagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    engagement_type = db.Column(db.String(50))  # statutory/internal/tax/GST
    period = db.Column(db.String(50))
    engagement_code = db.Column(db.String(50), unique=True)
    assigned_team = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    queries = db.relationship("QueryDoc", backref="engagement", lazy=True)


# ---------------------------------------------------------------------
# Module A: Query Framing (FR-01 to FR-06)
# ---------------------------------------------------------------------
class QueryDoc(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagement.id"), nullable=False)
    query_ref = db.Column(db.String(50), unique=True)
    audit_area = db.Column(db.String(100))
    description = db.Column(db.Text)
    tone = db.Column(db.String(20), default="formal")
    urgency = db.Column(db.String(20), default="normal")
    response_deadline_days = db.Column(db.Integer, default=3)
    generated_text = db.Column(db.Text)
    status = db.Column(db.String(20), default="draft")  # draft/sent/finalized
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------
# Module B: Email Drafting (FR-07 to FR-12)
# ---------------------------------------------------------------------
class EmailDoc(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email_type = db.Column(db.String(50))  # query/reminder1/reminder2/final/mrl/noc/closure
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagement.id"))
    query_ref = db.Column(db.String(50))
    recipient_name = db.Column(db.String(120))
    subject = db.Column(db.String(250))
    body = db.Column(db.Text)
    status = db.Column(db.String(20), default="draft")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------
# Module C: Bill / Invoice Formatting (FR-13 to FR-18)
# ---------------------------------------------------------------------
class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True)
    invoice_type = db.Column(db.String(20), default="invoice")  # invoice/debit_note/credit_note
    reference_invoice = db.Column(db.String(50))  # for debit/credit notes
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))
    engagement_id = db.Column(db.Integer, db.ForeignKey("engagement.id"))
    service_description = db.Column(db.Text)
    fee_amount = db.Column(db.Float, default=0)
    reimbursement = db.Column(db.Float, default=0)
    gst_rate = db.Column(db.Float, default=18.0)
    hsn_sac = db.Column(db.String(20), default="9982")
    tds_applicable = db.Column(db.Boolean, default=False)
    tds_rate = db.Column(db.Float, default=10.0)
    place_of_supply = db.Column(db.String(100))
    currency = db.Column(db.String(10), default="INR")
    taxable_value = db.Column(db.Float, default=0)
    tax_amount = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, default=0)
    amount_in_words = db.Column(db.String(400))
    status = db.Column(db.String(20), default="draft")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------
# Module D: Template & Clause Library (FR-19 to FR-21)
# ---------------------------------------------------------------------
class Template(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50))  # query/email/letter/checklist
    engagement_type = db.Column(db.String(50))
    content = db.Column(db.Text)
    version = db.Column(db.Integer, default=1)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------
# Module E: History, Traceability & Audit Trail (FR-22 to FR-24)
# ---------------------------------------------------------------------
class HistoryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doc_type = db.Column(db.String(20))  # query/email/invoice/template
    doc_id = db.Column(db.Integer)
    action = db.Column(db.String(30))  # created/edited/exported/sent/finalized/deleted
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    engagement_code = db.Column(db.String(50))
    details = db.Column(db.String(400))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
