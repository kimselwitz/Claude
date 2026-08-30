"""
Data access for Doorway. Plain functions over a sqlite3 connection -- no ORM,
so a non-engineer founder can read every query that touches participant data.
"""
from datetime import date, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

import db
import messaging

OPEN_STATUSES = ("open",)
CLOSED_STATUSES = ("received", "verified", "waived", "canceled")
COMPLETED_STATUSES = ("received", "verified")
STATUS_LABELS = {
    "open": "Waiting",
    "received": "Received",
    "verified": "Verified",
    "waived": "Waived",
    "canceled": "Canceled",
}


# --------------------------------------------------------------------------
# Organizations and users
# --------------------------------------------------------------------------

def get_org(conn, org_id):
    return conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()


def update_org(conn, org_id, name, timezone, quiet_start, quiet_end, sms_from):
    conn.execute(
        """UPDATE organizations
           SET name = ?, timezone = ?, quiet_start = ?, quiet_end = ?, sms_from = ?
           WHERE id = ?""",
        (name, timezone, quiet_start, quiet_end, sms_from, org_id))
    conn.commit()


def create_user(conn, org_id, username, password, full_name, role="staff"):
    cursor = conn.execute(
        """INSERT INTO users (org_id, username, password_hash, full_name, role)
           VALUES (?, ?, ?, ?, ?)""",
        (org_id, username, generate_password_hash(password), full_name, role))
    conn.commit()
    return cursor.lastrowid


def authenticate(conn, username, password):
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? AND active = 1", (username,)).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        return row
    return None


def get_user(conn, user_id):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


# --------------------------------------------------------------------------
# Contacts (participants in iteration 1)
# --------------------------------------------------------------------------

def list_contacts(conn, org_id, contact_type="participant", query=None,
                  language=None, include_archived=False):
    sql = "SELECT * FROM contacts WHERE org_id = ? AND contact_type = ?"
    params = [org_id, contact_type]
    if not include_archived:
        sql += " AND active = 1"
    if query:
        sql += (" AND (first_name LIKE ? OR last_name LIKE ? OR phone LIKE ?"
                " OR COALESCE(external_ref, '') LIKE ?)")
        like = "%%%s%%" % query
        params += [like, like, like, like]
    if language:
        sql += " AND preferred_language = ?"
        params.append(language)
    sql += " ORDER BY last_name, first_name"
    return conn.execute(sql, params).fetchall()


def get_contact(conn, org_id, contact_id):
    return conn.execute(
        "SELECT * FROM contacts WHERE id = ? AND org_id = ?", (contact_id, org_id)).fetchone()


def create_contact(conn, org_id, data, contact_type="participant"):
    phone = messaging.normalize_phone(data.get("phone"))
    consent = 1 if data.get("consent_sms") else 0
    cursor = conn.execute(
        """INSERT INTO contacts
           (org_id, contact_type, external_ref, first_name, last_name, phone, email,
            preferred_language, program, consent_sms, consent_at, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (org_id, contact_type, data.get("external_ref") or None,
         data["first_name"].strip(), data["last_name"].strip(), phone,
         data.get("email") or None, data.get("preferred_language") or "en",
         data.get("program") or None, consent, db.now_str() if consent else None,
         data.get("notes") or None))
    conn.commit()
    return cursor.lastrowid


def update_contact(conn, org_id, contact_id, data):
    existing = get_contact(conn, org_id, contact_id)
    consent = 1 if data.get("consent_sms") else 0
    consent_at = existing["consent_at"]
    if consent and not existing["consent_sms"]:
        consent_at = db.now_str()
    elif not consent:
        consent_at = None
    conn.execute(
        """UPDATE contacts
           SET external_ref = ?, first_name = ?, last_name = ?, phone = ?, email = ?,
               preferred_language = ?, program = ?, consent_sms = ?, consent_at = ?,
               notes = ?, active = ?
           WHERE id = ? AND org_id = ?""",
        (data.get("external_ref") or None, data["first_name"].strip(),
         data["last_name"].strip(), messaging.normalize_phone(data.get("phone")),
         data.get("email") or None, data.get("preferred_language") or "en",
         data.get("program") or None, consent, consent_at, data.get("notes") or None,
         1 if data.get("active", 1) else 0, contact_id, org_id))
    conn.commit()


def set_opt_out(conn, org_id, contact_id, opted_out):
    conn.execute(
        "UPDATE contacts SET opted_out = ?, opted_out_at = ? WHERE id = ? AND org_id = ?",
        (1 if opted_out else 0, db.now_str() if opted_out else None, contact_id, org_id))
    if opted_out:
        conn.execute(
            "UPDATE messages SET status = 'canceled' WHERE contact_id = ?"
            " AND direction = 'out' AND status IN ('queued', 'held')", (contact_id,))
    conn.commit()


# --------------------------------------------------------------------------
# Document types and requests
# --------------------------------------------------------------------------

def list_document_types(conn, org_id, include_inactive=False):
    sql = "SELECT * FROM document_types WHERE org_id = ?"
    if not include_inactive:
        sql += " AND active = 1"
    return conn.execute(sql + " ORDER BY name", (org_id,)).fetchall()


def create_document_type(conn, org_id, name, description=None):
    cursor = conn.execute(
        "INSERT INTO document_types (org_id, name, description) VALUES (?, ?, ?)",
        (org_id, name.strip(), description or None))
    conn.commit()
    return cursor.lastrowid


def set_document_type_active(conn, org_id, type_id, active):
    conn.execute("UPDATE document_types SET active = ? WHERE id = ? AND org_id = ?",
                 (1 if active else 0, type_id, org_id))
    conn.commit()


def document_type_names(conn, type_id):
    """{language: name} for one document type. English lives on the type itself."""
    return {row["language"]: row["name"] for row in conn.execute(
        "SELECT language, name FROM document_type_names WHERE document_type_id = ?", (type_id,))}


def save_document_type_names(conn, type_id, names):
    for language, name in names.items():
        if name and name.strip():
            conn.execute(
                """INSERT INTO document_type_names (document_type_id, language, name)
                   VALUES (?, ?, ?)
                   ON CONFLICT (document_type_id, language) DO UPDATE SET name = excluded.name""",
                (type_id, language, name.strip()))
        else:
            conn.execute(
                "DELETE FROM document_type_names WHERE document_type_id = ? AND language = ?",
                (type_id, language))
    conn.commit()


def localized_document_name(conn, type_id, language, fallback):
    """The document's name in `language`, or the English name if untranslated."""
    if not language or language == "en":
        return fallback
    row = conn.execute(
        "SELECT name FROM document_type_names WHERE document_type_id = ? AND language = ?",
        (type_id, language)).fetchone()
    return row["name"] if row else fallback


def document_name_coverage(conn, org_id):
    """{document_type_id: translated_language_count} for the document list page."""
    return {row["document_type_id"]: row["n"] for row in conn.execute(
        """SELECT n.document_type_id, COUNT(*) AS n
           FROM document_type_names n
           JOIN document_types d ON d.id = n.document_type_id
           WHERE d.org_id = ? GROUP BY n.document_type_id""", (org_id,))}


REQUEST_SELECT = """
    SELECT r.*, d.name AS document_name,
           c.first_name, c.last_name, c.phone, c.preferred_language,
           c.consent_sms, c.opted_out, c.active AS contact_active,
           julianday(r.due_date) - julianday(date('now')) AS days_until_due
    FROM document_requests r
    JOIN document_types d ON d.id = r.document_type_id
    JOIN contacts c ON c.id = r.contact_id
"""


def list_requests(conn, org_id, scope="open", contact_id=None, limit=None):
    """scope: open | overdue | due_soon | closed | all"""
    sql = REQUEST_SELECT + " WHERE r.org_id = ?"
    params = [org_id]
    if scope == "open":
        sql += " AND r.status = 'open'"
    elif scope == "overdue":
        sql += " AND r.status = 'open' AND r.due_date < date('now')"
    elif scope == "due_soon":
        sql += " AND r.status = 'open' AND r.due_date >= date('now')" \
               " AND r.due_date <= date('now', '+7 day')"
    elif scope == "closed":
        sql += " AND r.status <> 'open'"
    if contact_id:
        sql += " AND r.contact_id = ?"
        params.append(contact_id)
    sql += " ORDER BY (r.status = 'open') DESC, r.due_date ASC, r.id ASC"
    if limit:
        sql += " LIMIT %d" % int(limit)
    return conn.execute(sql, params).fetchall()


def get_request(conn, org_id, request_id):
    return conn.execute(REQUEST_SELECT + " WHERE r.org_id = ? AND r.id = ?",
                        (org_id, request_id)).fetchone()


def create_request(conn, org_id, contact_id, document_type_id, due_date,
                   requested_by=None, notes=None):
    cursor = conn.execute(
        """INSERT INTO document_requests
           (org_id, contact_id, document_type_id, status, due_date, requested_by, notes)
           VALUES (?, ?, ?, 'open', ?, ?, ?)""",
        (org_id, contact_id, document_type_id, due_date, requested_by, notes or None))
    conn.commit()
    return cursor.lastrowid


def set_request_status(conn, org_id, request_id, status):
    if status not in STATUS_LABELS:
        raise ValueError("unknown status: %s" % status)
    closed_at = None if status == "open" else db.now_str()
    conn.execute(
        "UPDATE document_requests SET status = ?, closed_at = ? WHERE id = ? AND org_id = ?",
        (status, closed_at, request_id, org_id))
    conn.commit()


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------

def list_templates(conn, org_id, category=None):
    sql = "SELECT * FROM message_templates WHERE org_id = ?"
    params = [org_id]
    if category:
        sql += " AND category = ?"
        params.append(category)
    return conn.execute(sql + " ORDER BY category, name", params).fetchall()


def get_template(conn, org_id, template_id):
    return conn.execute("SELECT * FROM message_templates WHERE id = ? AND org_id = ?",
                        (template_id, org_id)).fetchone()


def get_template_by_code(conn, org_id, code):
    return conn.execute("SELECT * FROM message_templates WHERE code = ? AND org_id = ?",
                        (code, org_id)).fetchone()


def template_variants(conn, template_id):
    return {row["language"]: row["body"] for row in conn.execute(
        "SELECT language, body FROM template_variants WHERE template_id = ?", (template_id,))}


def create_template(conn, org_id, code, name, category="document_request"):
    cursor = conn.execute(
        "INSERT INTO message_templates (org_id, code, name, category) VALUES (?, ?, ?, ?)",
        (org_id, code.strip(), name.strip(), category))
    conn.commit()
    return cursor.lastrowid


def save_variants(conn, template_id, bodies):
    """bodies: {language_code: text}. Empty text removes that language."""
    for language, body in bodies.items():
        if body and body.strip():
            conn.execute(
                """INSERT INTO template_variants (template_id, language, body)
                   VALUES (?, ?, ?)
                   ON CONFLICT (template_id, language) DO UPDATE SET body = excluded.body""",
                (template_id, language, body.strip()))
        else:
            conn.execute("DELETE FROM template_variants WHERE template_id = ? AND language = ?",
                         (template_id, language))
    conn.commit()


def translated_language_count(conn, template_id):
    return conn.execute(
        "SELECT COUNT(*) FROM template_variants WHERE template_id = ?",
        (template_id,)).fetchone()[0]


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------

def contact_thread(conn, contact_id, limit=100):
    return conn.execute(
        "SELECT * FROM messages WHERE contact_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
        (contact_id, limit)).fetchall()


def message_log(conn, org_id, direction=None, status=None, limit=200):
    sql = ("SELECT m.*, c.first_name, c.last_name, c.phone FROM messages m"
           " JOIN contacts c ON c.id = m.contact_id WHERE m.org_id = ?")
    params = [org_id]
    if direction:
        sql += " AND m.direction = ?"
        params.append(direction)
    if status:
        sql += " AND m.status = ?"
        params.append(status)
    sql += " ORDER BY m.created_at DESC, m.id DESC LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def unanswered_inbound(conn, org_id, limit=20):
    """Inbound replies with no outbound message after them -- the follow-up queue."""
    return conn.execute(
        """SELECT m.*, c.first_name, c.last_name, c.preferred_language
           FROM messages m
           JOIN contacts c ON c.id = m.contact_id
           WHERE m.org_id = ? AND m.direction = 'in'
             AND NOT EXISTS (
                 SELECT 1 FROM messages later
                 WHERE later.contact_id = m.contact_id AND later.direction = 'out'
                   AND later.created_at > m.created_at)
           ORDER BY m.created_at DESC LIMIT ?""", (org_id, limit)).fetchall()


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------

def log_action(conn, org_id, user_id, action, detail=None):
    conn.execute(
        "INSERT INTO audit_log (org_id, user_id, action, detail) VALUES (?, ?, ?, ?)",
        (org_id, user_id, action, detail))
    conn.commit()


def recent_audit(conn, org_id, limit=25):
    return conn.execute(
        """SELECT a.*, u.full_name FROM audit_log a
           LEFT JOIN users u ON u.id = a.user_id
           WHERE a.org_id = ? ORDER BY a.created_at DESC, a.id DESC LIMIT ?""",
        (org_id, limit)).fetchall()


# --------------------------------------------------------------------------
# Metrics -- the numbers a pilot gets renewed on
# --------------------------------------------------------------------------

def dashboard_metrics(conn, org_id):
    one = lambda sql, params=(): conn.execute(sql, (org_id,) + tuple(params)).fetchone()[0]

    open_count = one("SELECT COUNT(*) FROM document_requests WHERE org_id = ? AND status = 'open'")
    overdue = one("SELECT COUNT(*) FROM document_requests WHERE org_id = ? AND status = 'open'"
                  " AND due_date < date('now')")
    due_soon = one("SELECT COUNT(*) FROM document_requests WHERE org_id = ? AND status = 'open'"
                   " AND due_date >= date('now') AND due_date <= date('now', '+7 day')")

    turnaround = conn.execute(
        """SELECT julianday(closed_at) - julianday(requested_at) AS days
           FROM document_requests
           WHERE org_id = ? AND status IN ('received', 'verified')
             AND closed_at IS NOT NULL AND closed_at >= datetime('now', '-90 day')
           ORDER BY days""", (org_id,)).fetchall()
    days = [row["days"] for row in turnaround if row["days"] is not None]
    median_days = None
    if days:
        middle = len(days) // 2
        median_days = days[middle] if len(days) % 2 else (days[middle - 1] + days[middle]) / 2

    sent_30 = one("SELECT COUNT(*) FROM messages WHERE org_id = ? AND direction = 'out'"
                  " AND status IN ('sent', 'delivered') AND created_at >= datetime('now', '-30 day')")
    received_30 = one("SELECT COUNT(*) FROM messages WHERE org_id = ? AND direction = 'in'"
                      " AND created_at >= datetime('now', '-30 day')")
    failed_30 = one("SELECT COUNT(*) FROM messages WHERE org_id = ? AND direction = 'out'"
                    " AND status = 'failed' AND created_at >= datetime('now', '-30 day')")
    pending = one("SELECT COUNT(*) FROM messages WHERE org_id = ? AND direction = 'out'"
                  " AND status IN ('queued', 'held')")

    total_participants = one(
        "SELECT COUNT(*) FROM contacts WHERE org_id = ? AND contact_type = 'participant'"
        " AND active = 1")
    reachable = one(
        "SELECT COUNT(*) FROM contacts WHERE org_id = ? AND contact_type = 'participant'"
        " AND active = 1 AND consent_sms = 1 AND opted_out = 0 AND phone IS NOT NULL")

    by_language = conn.execute(
        """SELECT preferred_language, COUNT(*) AS n FROM contacts
           WHERE org_id = ? AND contact_type = 'participant' AND active = 1
           GROUP BY preferred_language ORDER BY n DESC""", (org_id,)).fetchall()
    non_english = sum(row["n"] for row in by_language if row["preferred_language"] != "en")

    return {
        "open_requests": open_count,
        "overdue_requests": overdue,
        "due_soon": due_soon,
        "median_days_to_receipt": round(median_days, 1) if median_days is not None else None,
        "completed_90d": len(days),
        "messages_sent_30d": sent_30,
        "replies_30d": received_30,
        "failed_30d": failed_30,
        "pending_messages": pending,
        "reply_rate": round(100.0 * received_30 / sent_30, 1) if sent_30 else None,
        "participants": total_participants,
        "reachable": reachable,
        "reachable_pct": round(100.0 * reachable / total_participants, 1)
        if total_participants else None,
        "by_language": by_language,
        "non_english": non_english,
    }


def default_due_date(days=10):
    return (date.today() + timedelta(days=days)).isoformat()
