"""
The reminder engine.

A nudge rule says: "for every <subject> that is <offset_days> from its date,
send <template> in the participant's language." Rules fire at most once per
(rule, subject) pair, so running the engine twice in a day is harmless.

Subjects are pluggable. Iteration 1 registers 'document_request'. Iteration 2
(appointment scheduling / no-show reduction) registers 'appointment' by adding
one class here and one table -- the rules, templates, language handling, consent
gate, quiet hours, and dispatch loop are already shared.
"""
from datetime import date, datetime

import db
import messaging
import models


def _parse_date(value):
    if isinstance(value, (date, datetime)):
        return value if isinstance(value, date) and not isinstance(value, datetime) else value.date()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


class DocumentRequestSubject:
    """Open document requests, keyed off their due date."""

    subject_type = "document_request"
    label = "Document request"
    date_label = "due date"

    def pending(self, conn, org_id):
        return conn.execute(
            """SELECT r.id, r.contact_id, r.due_date AS target_date, r.requested_at,
                      r.document_type_id, d.name AS document_name
               FROM document_requests r
               JOIN document_types d ON d.id = r.document_type_id
               WHERE r.org_id = ? AND r.status = 'open'""", (org_id,)).fetchall()

    def context(self, conn, row, contact, org):
        target = _parse_date(row["target_date"])
        delta = (target - date.today()).days
        # Name the document in the participant's language too -- a Spanish text
        # asking for "Proof of income" is not a translated message.
        document_name = models.localized_document_name(
            conn, row["document_type_id"], contact["preferred_language"], row["document_name"])
        return {
            "first_name": contact["first_name"],
            "last_name": contact["last_name"],
            "org_name": org["name"],
            "document_name": document_name,
            "due_date": target.strftime("%b %-d"),
            "due_date_iso": target.isoformat(),
            "days_until_due": delta,
            "days_overdue": -delta if delta < 0 else 0,
        }


REGISTRY = {}


def register(subject):
    REGISTRY[subject.subject_type] = subject


register(DocumentRequestSubject())


def subject_for(subject_type):
    return REGISTRY.get(subject_type)


def preview_context(subject_type):
    """Merge fields a template author can use for this subject type."""
    samples = {
        "document_request": {
            "first_name": "Ana", "last_name": "Reyes", "org_name": "Your agency",
            "document_name": "Pay stubs (last 30 days)", "due_date": "Sep 12",
            "due_date_iso": "2026-09-12", "days_until_due": 3, "days_overdue": 0,
        },
    }
    return samples.get(subject_type, {})


def run(conn, org_id, now=None, dry_run=False):
    """Evaluate every active rule and queue the messages that are due today.

    Returns a list of dicts describing what happened, so the UI can show
    "queued 6, skipped 2 (no consent)" rather than a silent success.
    """
    moment = now or db.now()
    today = moment.date()
    org = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
    rules = conn.execute(
        "SELECT * FROM nudge_rules WHERE org_id = ? AND active = 1 ORDER BY offset_days",
        (org_id,)).fetchall()

    results = []
    for rule in rules:
        subject = subject_for(rule["subject_type"])
        if subject is None:
            continue
        for row in subject.pending(conn, org_id):
            target = _parse_date(row["target_date"])
            if (target - today).days != rule["offset_days"]:
                continue
            already = conn.execute(
                "SELECT 1 FROM nudge_log WHERE rule_id = ? AND subject_type = ? AND subject_id = ?",
                (rule["id"], subject.subject_type, row["id"])).fetchone()
            if already:
                continue

            contact = conn.execute("SELECT * FROM contacts WHERE id = ?",
                                   (row["contact_id"],)).fetchone()
            outcome = {"rule": rule["name"], "contact_id": contact["id"],
                       "contact": "%s %s" % (contact["first_name"], contact["last_name"]),
                       "subject_id": row["id"]}

            ok, reason = messaging.reachability(contact)
            if not ok:
                outcome.update(status="skipped", reason=reason)
                results.append(outcome)
                continue

            language, body = messaging.pick_variant(
                conn, rule["template_code"], org_id, contact["preferred_language"])
            if not body:
                outcome.update(status="skipped",
                               reason="Template '%s' has no usable text" % rule["template_code"])
                results.append(outcome)
                continue

            rendered = messaging.render(body, subject.context(conn, row, contact, org))
            outcome.update(status="queued", language=language, preview=rendered)
            if not dry_run:
                message_id = messaging.queue_message(
                    conn, org, contact, rendered, language=language,
                    template_code=rule["template_code"], subject_type=subject.subject_type,
                    subject_id=row["id"], now=moment)
                conn.execute(
                    """INSERT INTO nudge_log (rule_id, subject_type, subject_id, message_id)
                       VALUES (?, ?, ?, ?)""",
                    (rule["id"], subject.subject_type, row["id"], message_id))
                conn.commit()
                outcome["message_id"] = message_id
            results.append(outcome)
    return results


def list_rules(conn, org_id):
    return conn.execute(
        """SELECT r.*, t.name AS template_name,
                  (SELECT COUNT(*) FROM nudge_log l WHERE l.rule_id = r.id) AS fired
           FROM nudge_rules r
           LEFT JOIN message_templates t
                  ON t.code = r.template_code AND t.org_id = r.org_id
           WHERE r.org_id = ? ORDER BY r.offset_days""", (org_id,)).fetchall()


def create_rule(conn, org_id, name, template_code, offset_days,
                subject_type="document_request"):
    cursor = conn.execute(
        """INSERT INTO nudge_rules (org_id, name, subject_type, template_code, offset_days)
           VALUES (?, ?, ?, ?, ?)""",
        (org_id, name.strip(), subject_type, template_code, int(offset_days)))
    conn.commit()
    return cursor.lastrowid


def set_rule_active(conn, org_id, rule_id, active):
    conn.execute("UPDATE nudge_rules SET active = ? WHERE id = ? AND org_id = ?",
                 (1 if active else 0, rule_id, org_id))
    conn.commit()


def describe_offset(offset_days):
    if offset_days > 0:
        return "%d day%s before" % (offset_days, "" if offset_days == 1 else "s")
    if offset_days == 0:
        return "on the day"
    n = -offset_days
    return "%d day%s after" % (n, "" if n == 1 else "s")
