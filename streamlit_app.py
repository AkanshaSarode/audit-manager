import os
import streamlit as st
from models import db, User, Client, Engagement, QueryDoc, EmailDoc, Invoice, Template, HistoryLog
from flask import Flask

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "auditdraft.db")


def create_flask_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def row_to_dict(obj, fields):
    return {field: getattr(obj, field, None) for field in fields}


app = create_flask_app()
st.set_page_config(page_title="AuditDraft Streamlit UI", layout="wide")
st.title("AuditDraft Assistant — Streamlit Dashboard")

if not os.path.exists(DB_PATH):
    st.warning(f"Database not found at: {DB_PATH}")
    st.stop()

with app.app_context():
    clients = Client.query.order_by(Client.name).all()
    engagements = Engagement.query.order_by(Engagement.created_at.desc()).all()
    queries = QueryDoc.query.order_by(QueryDoc.created_at.desc()).limit(50).all()
    emails = EmailDoc.query.order_by(EmailDoc.created_at.desc()).limit(50).all()
    invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(50).all()
    templates = Template.query.order_by(Template.updated_at.desc()).limit(50).all()
    history = HistoryLog.query.order_by(HistoryLog.timestamp.desc()).limit(100).all()

    st.header("AuditDraft Data Overview")
    col1, col2, col3 = st.columns(3)
    col1.metric("Clients", len(clients))
    col2.metric("Engagements", len(engagements))
    col3.metric("Queries", len(queries))

    st.markdown("---")
    st.subheader("Clients")
    st.table([row_to_dict(c, ["id", "name", "gstin", "pan", "contact_person", "contact_email"]) for c in clients])

    st.subheader("Engagements")
    st.table([row_to_dict(e, ["id", "client_id", "engagement_type", "period", "engagement_code", "assigned_team", "created_at"]) for e in engagements])

    st.subheader("Queries")
    st.table([row_to_dict(q, ["id", "query_ref", "engagement_id", "audit_area", "description", "tone", "urgency", "response_deadline_days", "created_at"]) for q in queries])

    st.subheader("Emails")
    st.table([row_to_dict(e, ["id", "email_type", "client_id", "engagement_id", "query_ref", "recipient_name", "subject", "status", "created_at"]) for e in emails])

    st.subheader("Invoices")
    st.table([row_to_dict(inv, ["id", "invoice_number", "invoice_type", "client_id", "service_description", "fee_amount", "tax_amount", "total_amount", "created_at"]) for inv in invoices])

    st.subheader("History")
    st.table([row_to_dict(h, ["id", "doc_type", "doc_id", "action", "user_id", "engagement_code", "details", "timestamp"]) for h in history])