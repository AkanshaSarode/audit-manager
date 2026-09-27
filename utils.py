"""
Utility functions supporting:
 - FR-04 Query numbering & referencing
 - FR-09 Subject line generation
 - FR-15 Auto invoice numbering
 - FR-18 Amount-in-words conversion (Indian numbering system)
 - FR-02 Auto-generated query text
 - FR-07..FR-11 Email template generation
"""
from datetime import datetime, timedelta

ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two_digit_words(n):
    if n < 20:
        return ONES[n]
    return (TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else "")).strip()


def _three_digit_words(n):
    if n >= 100:
        return (ONES[n // 100] + " Hundred" + (" " + _two_digit_words(n % 100) if n % 100 else "")).strip()
    return _two_digit_words(n)


def number_to_words_indian(amount) -> str:
    """Convert a rupee amount (float) into words using the Indian numbering
    system (lakh/crore), e.g. 1234567.50 -> 'Twelve Lakh Thirty Four Thousand
    Five Hundred Sixty Seven Rupees and Fifty Paise Only'."""
    amount = round(float(amount), 2)
    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))

    if rupees == 0:
        rupee_words = "Zero"
    else:
        crore = rupees // 10000000
        rupees %= 10000000
        lakh = rupees // 100000
        rupees %= 100000
        thousand = rupees // 1000
        rupees %= 1000
        hundred = rupees

        parts = []
        if crore:
            parts.append(_three_digit_words(crore) + " Crore")
        if lakh:
            parts.append(_three_digit_words(lakh) + " Lakh")
        if thousand:
            parts.append(_three_digit_words(thousand) + " Thousand")
        if hundred:
            parts.append(_three_digit_words(hundred))
        rupee_words = " ".join(parts).strip() or "Zero"

    words = f"Rupees {rupee_words}"
    if paise:
        words += f" and {_two_digit_words(paise)} Paise"
    words += " Only"
    return words


def generate_invoice_number(db, Invoice, branch="HO"):
    """FR-15: Sequential, non-duplicating invoice number per financial year
    (and branch). Indian FY runs Apr-Mar. Format: FIRM/FY24-25/HO/0001"""
    today = datetime.utcnow()
    if today.month >= 4:
        fy = f"{today.year % 100:02d}-{(today.year + 1) % 100:02d}"
    else:
        fy = f"{(today.year - 1) % 100:02d}-{today.year % 100:02d}"

    prefix = f"INV/FY{fy}/{branch}/"
    count = Invoice.query.filter(Invoice.invoice_number.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def generate_query_ref(engagement_code, sequence):
    """FR-04: unique query reference, linked to engagement code + sequence."""
    return f"{engagement_code}-Q{sequence:03d}"


def generate_subject_line(client_name, engagement_type, ref=None):
    """FR-09: firm-defined naming convention subject line."""
    base = f"[{client_name}] - [{engagement_type.title()} Audit]"
    if ref:
        base += f" - [{ref}]"
    return base


TONE_OPENERS = {
    "formal": "We are writing in connection with the {engagement_type} audit of {client_name}.",
    "very_formal": (
        "We refer to the ongoing {engagement_type} audit engagement of {client_name} "
        "and wish to bring the following matter to your kind attention."
    ),
}

URGENCY_LINE = {
    "normal": "We would appreciate your response at the earliest convenience.",
    "high": "This matter requires your prompt attention and a timely response.",
    "critical": "This is a time-sensitive matter and requires your immediate response.",
}


def generate_query_text(client_name, engagement_type, audit_area, description,
                         tone, urgency, query_ref, deadline_days):
    """FR-02: Auto-generated, professionally worded audit query."""
    opener = TONE_OPENERS.get(tone, TONE_OPENERS["formal"]).format(
        engagement_type=engagement_type, client_name=client_name
    )
    urgency_line = URGENCY_LINE.get(urgency, URGENCY_LINE["normal"])
    deadline = (datetime.utcnow() + timedelta(days=deadline_days)).strftime("%d-%b-%Y")

    text = f"""Query Reference: {query_ref}
Audit Area: {audit_area}

{opener}

During the course of our audit procedures, the following observation was noted:

"{description.strip()}"

We request you to kindly provide the relevant supporting documents, explanations,
and/or management clarification in respect of the above observation.

{urgency_line} Kindly furnish your response / supporting documentation on or
before {deadline}.

Please feel free to reach out should you require any clarification regarding
the above query.
"""
    return text.strip()


# ---------------------------------------------------------------------
# Module B: Email templates (FR-07)
# ---------------------------------------------------------------------
EMAIL_TEMPLATES = {
    "query": {
        "label": "Query Email",
        "body": (
            "Dear {recipient_name},\n\n"
            "Greetings from {firm_name}.\n\n"
            "With reference to the ongoing {engagement_type} audit of {client_name}, "
            "please find below our query for your kind attention and response:\n\n"
            "{query_text}\n\n"
            "We look forward to your response at the earliest.\n\n"
            "Warm regards,"
        ),
    },
    "reminder1": {
        "label": "1st Reminder",
        "body": (
            "Dear {recipient_name},\n\n"
            "This is a gentle reminder regarding our query dated below, for which we are "
            "yet to receive your response.\n\n"
            "Query Reference: {query_ref}\n\n"
            "{query_text}\n\n"
            "We would be grateful if you could share the requested information at the "
            "earliest so that we may proceed with our audit procedures without delay.\n\n"
            "Warm regards,"
        ),
    },
    "reminder2": {
        "label": "2nd Reminder",
        "body": (
            "Dear {recipient_name},\n\n"
            "We refer to our earlier communications regarding query {query_ref}, to "
            "which a response is still awaited.\n\n"
            "{query_text}\n\n"
            "We request you to treat this as a priority matter and revert at the "
            "earliest, as any further delay may impact our audit timelines.\n\n"
            "Regards,"
        ),
    },
    "final_notice": {
        "label": "Final Notice",
        "body": (
            "Dear {recipient_name},\n\n"
            "Despite our earlier reminders, we have not yet received a response to "
            "query {query_ref}.\n\n"
            "{query_text}\n\n"
            "Please treat this as a final notice. We request an immediate response, "
            "failing which we will be constrained to report this matter as an "
            "unresolved item in our audit documentation.\n\n"
            "Regards,"
        ),
    },
    "mrl": {
        "label": "Management Representation Request",
        "body": (
            "Dear {recipient_name},\n\n"
            "As part of the completion procedures for the {engagement_type} audit of "
            "{client_name}, we request management to provide a signed Management "
            "Representation Letter (MRL) covering the matters discussed during the "
            "course of the audit.\n\n"
            "We would appreciate receiving the signed MRL at your earliest convenience "
            "to enable us to finalize our audit report.\n\n"
            "Warm regards,"
        ),
    },
    "noc": {
        "label": "NOC Request",
        "body": (
            "Dear {recipient_name},\n\n"
            "We request you to kindly issue a No Objection Certificate (NOC) in "
            "connection with {client_name}, as required for our records / "
            "professional clearance purposes.\n\n"
            "Kindly let us know if any additional information is required from our end.\n\n"
            "Warm regards,"
        ),
    },
    "closure": {
        "label": "Closure / Thank-you",
        "body": (
            "Dear {recipient_name},\n\n"
            "We would like to thank you and your team for the support and cooperation "
            "extended during the {engagement_type} audit of {client_name}. All "
            "outstanding queries have been satisfactorily resolved.\n\n"
            "We look forward to continued association.\n\n"
            "Warm regards,"
        ),
    },
}


def generate_email_body(email_type, **context):
    template = EMAIL_TEMPLATES.get(email_type, EMAIL_TEMPLATES["query"])["body"]
    safe_context = {k: (v if v is not None else "") for k, v in context.items()}
    try:
        return template.format(**safe_context)
    except KeyError:
        return template


def signature_block(user):
    """FR-10: standard signature block appended automatically."""
    return (
        f"{user.name}\n"
        f"{user.designation}\n"
        f"{user.firm_name}\n"
        f"{user.email or ''}\n"
        f"--\nThis email and any attachments are confidential and intended solely "
        f"for the addressee(s)."
    )
