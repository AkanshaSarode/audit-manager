# AuditDraft Assistant

A working MVP implementation of the **Query Framing & Document Formatting Assistant Bot**
described in the SRS (v1.0) for audit departments and CA practices.

Built with **Python + Flask + PostgreSQL**. AI/LLM-based generation (mentioned as optional in the SRS, section 2.6)
is **not required** — this MVP uses rule-based, template-driven generation for queries,
emails, and invoices, which is deterministic, fast, and doesn't need an API key. You can
later swap in an LLM call inside `utils.py` (`generate_query_text`, `generate_email_body`)
if you want AI-assisted phrasing.

## What's implemented (mapped to the SRS)

| SRS Module | Status |
|---|---|
| 3.1 Module A — Query Framing Engine (FR-01–FR-06) | ✅ Implemented (FR-06 clause suggestions is a stub/TODO) |
| 3.2 Module B — Email Drafting & Formatting (FR-07–FR-12) | ✅ Implemented |
| 3.3 Module C — Bill/Invoice Formatting (FR-13–FR-18) | ✅ Implemented (FR-17 multi-currency: field present, no live FX conversion) |
| 3.4 Module D — Template & Clause Library (FR-19–FR-21) | ✅ Implemented |
| 3.5 Module E — History, Traceability & Audit Trail (FR-22–FR-24) | ✅ Implemented |
| 3.6 Module F — User & Access Management (FR-25–FR-27) | ✅ Implemented (role-based access + login). Approval workflow FR-26 is a TODO. |
| 3.7 Module G — Export & Integration (FR-28–FR-30) | ✅ FR-28/29 implemented (.docx/.pdf export, copy-from-textbox). FR-30 direct email send is a TODO (would use Outlook/Gmail API). |

## Project Structure

```
auditdraft_assistant/
├── app.py              # Flask app & all routes
├── models.py            # SQLAlchemy models (DB schema)
├── utils.py              # Query/email text generation, invoice numbering, amount-in-words
├── exporters.py          # .docx / .pdf export logic
├── req.txt
├── templates/            # Jinja2 HTML templates (Bootstrap 5 UI)
└── static/style.css
```

## Setup (VS Code / local machine)

This app requires PostgreSQL — it will refuse to start if `DATABASE_URL` isn't set (no SQLite fallback).

1. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Get a local Postgres database.** Easiest via Docker:
   ```bash
   docker run --name auditdraft-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=auditdraft -p 5432:5432 -d postgres:16
   ```
   Then set the connection string (e.g. in a `.env` file, since `python-dotenv` is already a dependency):
   ```
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/auditdraft
   ```

4. **Initialize the database** (creates tables + a default admin user):
   ```bash
   flask --app app.py init-db
   ```
   This creates a default login: **username: `admin`, password: `admin123`**
   (change this immediately after first login by editing the DB or adding a
   "change password" route).

   Alternatively, just run the app directly — it auto-creates the tables and admin
   user on first run (see the `if __name__ == "__main__":` block in `app.py`).

5. **Run the app**:
   ```bash
   python app.py
   ```
   or
   ```bash
   flask --app app.py run --debug
   ```

5. Open your browser at **http://127.0.0.1:5000**

## First-time usage flow

1. Log in with the initial admin account (local default: `admin` / `admin123`; Render uses the username and password you configured), or register an executive account.
2. Go to **Clients** → add a client (name, GSTIN, PAN, contact).
3. Go to **Engagements** → create an engagement for that client (e.g. Statutory Audit,
   engagement code like `CLT01-SA-2526`).
4. Go to **New Query** → select the engagement, describe the observation → the bot
   generates a formatted, numbered audit query (FR-01–FR-04).
5. From the query view, click **Convert to Email** to turn it into a client-ready
   email (auto-fills subject, body, signature block) — or go to **Draft Email**
   directly for reminders, MRL requests, NOC requests, etc.
6. Go to **Invoice/Bill** → enter fee/GST details → the bot generates a
   GST-compliant invoice with auto-numbering and amount-in-words.
7. Check **Audit Trail** to see the full history log of every document created,
   edited, or exported (FR-22–FR-24).
8. Admin/Manager users can manage the **Template Library** (FR-19–FR-21).

## Deploy on Render

This repository includes a Render Blueprint in `render.yaml`. Push the project to GitHub, choose **New → Blueprint** in Render, and connect that repository. Render will create the Flask web service and a PostgreSQL database. During setup, enter a strong value for `INITIAL_ADMIN_PASSWORD`; `admin` is the initial username. The Blueprint generates `SECRET_KEY` for you.

The web service is configured on Render's free tier for a demo; it may spin down when idle. The database is configured on Render's smallest paid plan so data persists. Do not switch the database to Render's free plan for real audit/client data: free Postgres expires after 30 days. For production use, upgrade the web service too, enable backups, and review security and privacy requirements before storing client records.

The app uses PostgreSQL everywhere (Render and local dev) — see the local setup steps above for running Postgres in Docker.

## Notes on scope / next steps

- **Regulatory disclaimer (per SRS section 8.1):** All generated content is a
  *drafting aid only*. It is not a substitute for professional review — every
  document should be reviewed by the responsible CA/auditor before being sent
  to a client, exactly as flagged as the #1 risk in the SRS.
- **Security (SRS 5.2):** This MVP uses Flask-Login with hashed passwords and a
  SQLite DB. For production, add HTTPS/TLS termination (e.g. via a reverse
  proxy), stronger secret-key management (env vars, not hardcoded), and
  encryption-at-rest for the database if hosting client-sensitive data.
- **FR-06 / FR-17 / FR-26 / FR-30** are intentionally left as clearly marked
  stubs/TODOs — they depend on decisions still open in SRS section 8.2
  (e.g. whether direct email-send integration is needed for v1.0).
- To swap in real AI-assisted drafting (SRS 2.6 "language-model API"), replace
  the body of `generate_query_text()` / `generate_email_body()` in `utils.py`
  with a call to the Anthropic API (or your provider of choice), keeping the
  same function signature so the rest of the app doesn't need to change.
