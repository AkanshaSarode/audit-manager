import os
from functools import wraps
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, request, flash, send_file, abort
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import (
    db, User, Client, Engagement, QueryDoc, EmailDoc, Invoice, Template, HistoryLog
)
from utils import (
    number_to_words_indian, generate_invoice_number, generate_query_ref,
    generate_subject_line, generate_query_text, generate_email_body,
    signature_block, EMAIL_TEMPLATES,
)
from exporters import (
    export_text_docx, export_text_pdf, export_invoice_docx, export_invoice_pdf
)

BASE_DIR = os.path.dirname(__file__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not set. This app requires PostgreSQL — set DATABASE_URL "
        "to a postgres connection string (e.g. postgresql://user:pass@host:5432/dbname). "
        "On Render this is provided automatically by render.yaml; for local development, "
        "run a local Postgres instance (or use Docker) and export DATABASE_URL yourself."
    )
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
elif not database_url.startswith("postgresql+psycopg://"):
    raise RuntimeError(
        "DATABASE_URL must be a PostgreSQL connection string "
        "(postgres://... or postgresql://...); other database backends are not supported."
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------
# FR-25: Role-based access control decorator
# ---------------------------------------------------------------------
def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def log_history(doc_type, doc_id, action, engagement_code=None, details=""):
    """FR-22: Log every generated document with timestamp, author, status."""
    entry = HistoryLog(
        doc_type=doc_type, doc_id=doc_id, action=action,
        user_id=current_user.id if current_user.is_authenticated else None,
        engagement_code=engagement_code, details=details,
    )
    db.session.add(entry)
    db.session.commit()


# =======================================================================
# AUTH
# =======================================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if User.query.filter_by(username=request.form["username"]).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("register"))
        user = User(
            name=request.form["name"],
            username=request.form["username"],
            email=request.form.get("email"),
            password_hash=generate_password_hash(request.form["password"]),
            role="executive",
            designation=request.form.get("designation", "Audit Executive"),
            firm_name=request.form.get("firm_name", "Your CA Firm"),
        )
        db.session.add(user)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and check_password_hash(user.password_hash, request.form["password"]):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# =======================================================================
# DASHBOARD
# =======================================================================
@app.route("/")
@login_required
def dashboard():
    stats = {
        "clients": Client.query.count(),
        "queries": QueryDoc.query.count(),
        "emails": EmailDoc.query.count(),
        "invoices": Invoice.query.count(),
    }
    recent = HistoryLog.query.order_by(HistoryLog.timestamp.desc()).limit(10).all()
    return render_template("index.html", stats=stats, recent=recent)


# =======================================================================
# CLIENTS & ENGAGEMENTS (supporting data)
# =======================================================================
@app.route("/clients", methods=["GET", "POST"])
@login_required
def clients():
    if request.method == "POST":
        c = Client(
            name=request.form["name"], gstin=request.form.get("gstin"),
            pan=request.form.get("pan"), address=request.form.get("address"),
            contact_person=request.form.get("contact_person"),
            contact_email=request.form.get("contact_email"),
        )
        db.session.add(c)
        db.session.commit()
        flash("Client added.", "success")
        return redirect(url_for("clients"))
    all_clients = Client.query.order_by(Client.name).all()
    return render_template("clients.html", clients=all_clients)


@app.route("/engagements", methods=["GET", "POST"])
@login_required
def engagements():
    if request.method == "POST":
        code = request.form["engagement_code"]
        if Engagement.query.filter_by(engagement_code=code).first():
            flash("Engagement code already exists.", "danger")
        else:
            e = Engagement(
                client_id=request.form["client_id"],
                engagement_type=request.form["engagement_type"],
                period=request.form.get("period"),
                engagement_code=code,
                assigned_team=request.form.get("assigned_team"),
            )
            db.session.add(e)
            db.session.commit()
            flash("Engagement created.", "success")
        return redirect(url_for("engagements"))
    all_engagements = Engagement.query.order_by(Engagement.created_at.desc()).all()
    all_clients = Client.query.order_by(Client.name).all()
    return render_template("engagements.html", engagements=all_engagements, clients=all_clients)


# =======================================================================
# MODULE A: QUERY FRAMING (FR-01 .. FR-06)
# =======================================================================
@app.route("/query/new", methods=["GET", "POST"])
@login_required
def query_new():
    all_engagements = Engagement.query.all()
    generated = None
    if request.method == "POST":
        engagement = Engagement.query.get_or_404(int(request.form["engagement_id"]))
        client = engagement.client

        seq = QueryDoc.query.filter_by(engagement_id=engagement.id).count() + 1
        query_ref = generate_query_ref(engagement.engagement_code, seq)  # FR-04
        tone = request.form.get("tone", "formal")
        urgency = request.form.get("urgency", "normal")
        deadline_days = int(request.form.get("deadline_days", 3))
        audit_area = request.form["audit_area"]
        description = request.form["description"]

        text = generate_query_text(  # FR-02
            client.name, engagement.engagement_type, audit_area, description,
            tone, urgency, query_ref, deadline_days,
        )

        q = QueryDoc(
            engagement_id=engagement.id, query_ref=query_ref, audit_area=audit_area,
            description=description, tone=tone, urgency=urgency,
            response_deadline_days=deadline_days, generated_text=text,
            created_by=current_user.id,
        )
        db.session.add(q)
        db.session.commit()
        log_history("query", q.id, "created", engagement.engagement_code, query_ref)
        flash(f"Query {query_ref} generated.", "success")
        return redirect(url_for("query_view", query_id=q.id))

    return render_template("query_form.html", engagements=all_engagements)


@app.route("/query/<int:query_id>")
@login_required
def query_view(query_id):
    q = QueryDoc.query.get_or_404(query_id)
    return render_template("query_view.html", q=q)


@app.route("/query/<int:query_id>/edit", methods=["POST"])
@login_required
def query_edit(query_id):
    q = QueryDoc.query.get_or_404(query_id)
    q.generated_text = request.form["generated_text"]
    db.session.commit()
    log_history("query", q.id, "edited", q.engagement.engagement_code)
    flash("Query updated.", "success")
    return redirect(url_for("query_view", query_id=q.id))


@app.route("/query/list")
@login_required
def query_list():
    q = request.args.get("q", "")
    query = QueryDoc.query
    if q:
        query = query.filter(QueryDoc.description.ilike(f"%{q}%") |
                              QueryDoc.query_ref.ilike(f"%{q}%"))
    docs = query.order_by(QueryDoc.created_at.desc()).all()
    return render_template("query_list.html", docs=docs, q=q)


# =======================================================================
# MODULE B: EMAIL DRAFTING (FR-07 .. FR-12)
# =======================================================================
@app.route("/email/new", methods=["GET", "POST"])
@login_required
def email_new():
    all_clients = Client.query.all()
    all_queries = QueryDoc.query.order_by(QueryDoc.created_at.desc()).all()
    preview = None
    if request.method == "POST":
        client = Client.query.get_or_404(int(request.form["client_id"]))
        engagement_id = request.form.get("engagement_id") or None
        engagement = Engagement.query.get(int(engagement_id)) if engagement_id else None
        email_type = request.form["email_type"]
        query_id = request.form.get("query_id") or None
        query_doc = QueryDoc.query.get(int(query_id)) if query_id else None

        subject = generate_subject_line(  # FR-09
            client.name,
            engagement.engagement_type if engagement else "Engagement",
            query_doc.query_ref if query_doc else None,
        )
        body = generate_email_body(  # FR-07/FR-08
            email_type,
            recipient_name=request.form.get("recipient_name", client.contact_person),
            firm_name=current_user.firm_name,
            engagement_type=engagement.engagement_type if engagement else "",
            client_name=client.name,
            query_ref=query_doc.query_ref if query_doc else "",
            query_text=query_doc.generated_text if query_doc else request.form.get("custom_text", ""),
        )
        body += "\n\n" + signature_block(current_user)  # FR-10

        e = EmailDoc(
            email_type=email_type, client_id=client.id, engagement_id=engagement.id if engagement else None,
            query_ref=query_doc.query_ref if query_doc else None,
            recipient_name=request.form.get("recipient_name", client.contact_person),
            subject=subject, body=body, created_by=current_user.id,
        )
        db.session.add(e)
        db.session.commit()
        log_history("email", e.id, "created",
                    engagement.engagement_code if engagement else None, subject)
        preview = e
        return redirect(url_for("email_view", email_id=e.id))

    return render_template(
        "email_form.html", clients=all_clients, queries=all_queries,
        email_types=EMAIL_TEMPLATES,
    )


@app.route("/email/<int:email_id>")
@login_required
def email_view(email_id):
    e = EmailDoc.query.get_or_404(email_id)
    return render_template("email_view.html", e=e)


@app.route("/email/<int:email_id>/edit", methods=["POST"])
@login_required
def email_edit(email_id):
    e = EmailDoc.query.get_or_404(email_id)
    e.subject = request.form["subject"]
    e.body = request.form["body"]
    db.session.commit()
    log_history("email", e.id, "edited")
    flash("Email updated.", "success")
    return redirect(url_for("email_view", email_id=e.id))


@app.route("/email/<int:email_id>/mark_sent")
@login_required
def email_mark_sent(email_id):
    e = EmailDoc.query.get_or_404(email_id)
    e.status = "sent"
    db.session.commit()
    log_history("email", e.id, "sent")
    flash("Marked as sent.", "success")
    return redirect(url_for("email_view", email_id=e.id))


# =======================================================================
# MODULE C: BILL / INVOICE FORMATTING (FR-13 .. FR-18)
# =======================================================================
@app.route("/invoice/new", methods=["GET", "POST"])
@login_required
def invoice_new():
    all_clients = Client.query.all()
    all_invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(20).all()
    clients_map = {c.id: c.name for c in all_clients}
    if request.method == "POST":
        client = Client.query.get_or_404(int(request.form["client_id"]))
        engagement_id = request.form.get("engagement_id") or None

        fee = float(request.form.get("fee_amount", 0) or 0)
        reimbursement = float(request.form.get("reimbursement", 0) or 0)
        gst_rate = float(request.form.get("gst_rate", 18) or 0)
        tds_applicable = bool(request.form.get("tds_applicable"))
        tds_rate = float(request.form.get("tds_rate", 10) or 0)
        invoice_type = request.form.get("invoice_type", "invoice")

        taxable_value = fee + reimbursement  # FR-14 statutory computation
        tax_amount = round(taxable_value * gst_rate / 100, 2)
        total_amount = round(taxable_value + tax_amount, 2)

        invoice_number = generate_invoice_number(db, Invoice)  # FR-15

        inv = Invoice(
            invoice_number=invoice_number,
            invoice_type=invoice_type,
            reference_invoice=request.form.get("reference_invoice"),
            client_id=client.id,
            engagement_id=int(engagement_id) if engagement_id else None,
            service_description=request.form["service_description"],
            fee_amount=fee, reimbursement=reimbursement,
            gst_rate=gst_rate, hsn_sac=request.form.get("hsn_sac", "9982"),
            tds_applicable=tds_applicable, tds_rate=tds_rate,
            place_of_supply=request.form.get("place_of_supply"),
            currency=request.form.get("currency", "INR"),
            taxable_value=taxable_value, tax_amount=tax_amount,
            total_amount=total_amount,
            amount_in_words=number_to_words_indian(total_amount),  # FR-18
            created_by=current_user.id,
        )
        db.session.add(inv)
        db.session.commit()
        log_history("invoice", inv.id, "created", details=invoice_number)
        flash(f"Invoice {invoice_number} generated.", "success")
        return redirect(url_for("invoice_view", invoice_id=inv.id))

    return render_template("invoice_form.html", clients=all_clients, invoices=all_invoices, clients_map=clients_map)


@app.route("/invoice/<int:invoice_id>")
@login_required
def invoice_view(invoice_id):
    inv = Invoice.query.get_or_404(invoice_id)
    client = Client.query.get(inv.client_id)
    return render_template("invoice_view.html", inv=inv, client=client)


# =======================================================================
# MODULE D: TEMPLATE & CLAUSE LIBRARY (FR-19 .. FR-21)
# =======================================================================
@app.route("/templates", methods=["GET", "POST"])
@login_required
def templates_library():
    if request.method == "POST":
        roles_ok = current_user.role in ("admin", "manager")
        if not roles_ok:
            flash("Only Admin/Manager can add templates.", "danger")
            return redirect(url_for("templates_library"))
        t = Template(
            name=request.form["name"], category=request.form["category"],
            engagement_type=request.form.get("engagement_type"),
            content=request.form["content"], created_by=current_user.id,
        )
        db.session.add(t)
        db.session.commit()
        log_history("template", t.id, "created", details=t.name)
        flash("Template added.", "success")
        return redirect(url_for("templates_library"))

    q = request.args.get("q", "")
    query = Template.query
    if q:
        query = query.filter(Template.name.ilike(f"%{q}%"))
    all_templates = query.order_by(Template.updated_at.desc()).all()
    return render_template("templates_library.html", templates=all_templates, q=q)


@app.route("/templates/<int:template_id>/edit", methods=["POST"])
@login_required
@roles_required("admin", "manager")
def template_edit(template_id):
    t = Template.query.get_or_404(template_id)
    t.content = request.form["content"]
    t.version += 1  # FR-21 version control
    t.updated_at = datetime.utcnow()
    db.session.commit()
    log_history("template", t.id, "edited", details=f"v{t.version}")
    flash("Template updated.", "success")
    return redirect(url_for("templates_library"))


@app.route("/templates/<int:template_id>/delete")
@login_required
@roles_required("admin", "manager")
def template_delete(template_id):
    t = Template.query.get_or_404(template_id)
    db.session.delete(t)
    db.session.commit()
    log_history("template", template_id, "deleted", details=t.name)
    flash("Template removed.", "success")
    return redirect(url_for("templates_library"))


# =======================================================================
# MODULE E: HISTORY / AUDIT TRAIL (FR-22 .. FR-24)
# =======================================================================
@app.route("/history")
@login_required
def history():
    q = request.args.get("q", "")
    doc_type = request.args.get("doc_type", "")
    query = HistoryLog.query
    if q:
        query = query.filter(HistoryLog.details.ilike(f"%{q}%") |
                              HistoryLog.engagement_code.ilike(f"%{q}%"))
    if doc_type:
        query = query.filter(HistoryLog.doc_type == doc_type)
    logs = query.order_by(HistoryLog.timestamp.desc()).limit(300).all()
    return render_template("history.html", logs=logs, q=q, doc_type=doc_type)


# =======================================================================
# MODULE G: EXPORT (FR-28 / FR-29)
# =======================================================================
@app.route("/export/query/<int:query_id>/<fmt>")
@login_required
def export_query(query_id, fmt):
    q = QueryDoc.query.get_or_404(query_id)
    fname = f"query_{q.query_ref}.{fmt}"
    if fmt == "docx":
        path = export_text_docx(f"Audit Query - {q.query_ref}", q.generated_text, fname)
    elif fmt == "pdf":
        path = export_text_pdf(f"Audit Query - {q.query_ref}", q.generated_text, fname)
    else:
        abort(400)
    log_history("query", q.id, "exported", q.engagement.engagement_code, fmt)
    return send_file(path, as_attachment=True)


@app.route("/export/email/<int:email_id>/<fmt>")
@login_required
def export_email(email_id, fmt):
    e = EmailDoc.query.get_or_404(email_id)
    fname = f"email_{e.id}.{fmt}"
    if fmt == "docx":
        path = export_text_docx(e.subject, e.body, fname)
    elif fmt == "pdf":
        path = export_text_pdf(e.subject, e.body, fname)
    else:
        abort(400)
    log_history("email", e.id, "exported", details=fmt)
    return send_file(path, as_attachment=True)


@app.route("/export/invoice/<int:invoice_id>/<fmt>")
@login_required
def export_invoice(invoice_id, fmt):
    inv = Invoice.query.get_or_404(invoice_id)
    client = Client.query.get(inv.client_id)
    fname = f"invoice_{inv.invoice_number.replace('/', '-')}.{fmt}"
    if fmt == "docx":
        path = export_invoice_docx(inv, client, current_user.firm_name, fname)
    elif fmt == "pdf":
        path = export_invoice_pdf(inv, client, current_user.firm_name, fname)
    else:
        abort(400)
    log_history("invoice", inv.id, "exported", details=fmt)
    return send_file(path, as_attachment=True)


# =======================================================================
# CLI: init-db
# =======================================================================
def initialize_database():
    db.create_all()
    admin_username = os.environ.get("INITIAL_ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "admin123")
    if not User.query.filter_by(username=admin_username).first():
        admin = User(
            name="Firm Admin", username=admin_username, email="admin@firm.com",
            password_hash=generate_password_hash(admin_password),
            role="admin", designation="Admin", firm_name="Your CA Firm",
        )
        db.session.add(admin)
        db.session.commit()
        print(f"Created initial admin user: {admin_username}")
    print("Database initialized.")


@app.cli.command("init-db")
def init_db():
    """Run with: flask --app app.py init-db"""
    initialize_database()


if __name__ == "__main__":
    with app.app_context():
        initialize_database()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
    )
