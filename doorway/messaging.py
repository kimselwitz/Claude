"""
Outbound/inbound SMS: rendering, consent gates, quiet hours, and delivery.

Everything that actually leaves the building goes through queue_message() ->
dispatch_due(). That single choke point is where consent, opt-out, quiet hours,
and provider errors are enforced, so no caller can accidentally text someone who
asked not to be texted.
"""
import os
import re
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import db
import languages

MERGE_PATTERN = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")

# Keyword handling for inbound replies. Carriers honor English STOP already;
# we honor the same intent expressed in the languages we serve.
STOP_WORDS = {
    "stop", "stopall", "unsubscribe", "cancel", "end", "quit",
    "alto", "pare", "parar", "basta",
    "arret", "arreter",
    "joogso", "jooji",
    "kufa",
}
START_WORDS = {"start", "unstop", "yes", "si", "oui", "haa", "iyaa"}
HELP_WORDS = {"help", "info", "ayuda", "aide", "ajuda", "caawimo"}


class SendResult:
    def __init__(self, ok, provider_ref=None, error=None):
        self.ok = ok
        self.provider_ref = provider_ref
        self.error = error


class ConsoleProvider:
    """Default provider: records the send without touching the network.

    This is what demos, pilots, and the test suite run on. Messages still move
    through the full queue/consent/quiet-hours path, they just land in the log
    instead of on a phone.
    """

    name = "console"

    def send(self, to, body, sms_from=None):
        print("[doorway sms] to=%s from=%s: %s" % (to, sms_from, body))
        return SendResult(True, provider_ref="console-%s" % db.now().strftime("%Y%m%d%H%M%S"))


class TwilioProvider:
    """Live provider. Configured entirely by environment variables:

        DOORWAY_SMS_PROVIDER=twilio
        TWILIO_ACCOUNT_SID=...
        TWILIO_AUTH_TOKEN=...
        TWILIO_FROM=+12075550123      (or set sms_from per organization)

    Uses urllib so the app keeps a two-package dependency list.
    """

    name = "twilio"
    API = "https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json"

    def __init__(self, account_sid=None, auth_token=None, default_from=None):
        self.account_sid = account_sid or os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.default_from = default_from or os.environ.get("TWILIO_FROM", "")

    def send(self, to, body, sms_from=None):
        if not (self.account_sid and self.auth_token):
            return SendResult(False, error="Twilio credentials are not configured")
        payload = urllib.parse.urlencode({
            "To": to,
            "From": sms_from or self.default_from,
            "Body": body,
        }).encode("utf-8")
        request = urllib.request.Request(self.API % self.account_sid, data=payload)
        credentials = "%s:%s" % (self.account_sid, self.auth_token)
        import base64
        request.add_header("Authorization", "Basic " + base64.b64encode(
            credentials.encode("utf-8")).decode("ascii"))
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
            return SendResult(True, provider_ref=data.get("sid"))
        except Exception as exc:                      # noqa: BLE001 - surfaced to the message row
            return SendResult(False, error=str(exc)[:500])


def get_provider():
    if os.environ.get("DOORWAY_SMS_PROVIDER", "console").lower() == "twilio":
        return TwilioProvider()
    return ConsoleProvider()


# --------------------------------------------------------------------------
# Phone numbers
# --------------------------------------------------------------------------

def normalize_phone(raw):
    """Best-effort E.164 for US/CA numbers; returns None if it can't be parsed."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if raw.strip().startswith("+"):
        return "+" + digits if digits else None
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits if digits else None


def format_phone(value):
    """Display form for a stored E.164 number."""
    if not value:
        return ""
    if value.startswith("+1") and len(value) == 12:
        return "(%s) %s-%s" % (value[2:5], value[5:8], value[8:])
    return value


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render(body, context):
    """Substitute {{field}} merge tags. Unknown tags are left visible on
    purpose -- a staff member seeing '{{due_date}}' in a preview is far better
    than a participant receiving a blank."""
    def replace(match):
        key = match.group(1)
        value = context.get(key)
        return "" if value is None else str(value)
    return MERGE_PATTERN.sub(replace, body)


def merge_fields(body):
    return sorted(set(MERGE_PATTERN.findall(body or "")))


def pick_variant(conn, template_code, org_id, language):
    """Return (language_used, body) for a template, falling back to English."""
    row = conn.execute(
        "SELECT id FROM message_templates WHERE org_id = ? AND code = ? AND active = 1",
        (org_id, template_code)).fetchone()
    if not row:
        return None, None
    variants = {
        v["language"]: v["body"]
        for v in conn.execute(
            "SELECT language, body FROM template_variants WHERE template_id = ?",
            (row["id"],))
    }
    if language in variants and variants[language].strip():
        return language, variants[language]
    fallback = languages.DEFAULT_LANGUAGE
    if fallback in variants:
        return fallback, variants[fallback]
    return (None, None)


# --------------------------------------------------------------------------
# Quiet hours
# --------------------------------------------------------------------------

def in_quiet_hours(moment, quiet_start, quiet_end):
    """Quiet hours wrap midnight: start 21, end 8 means 21:00-07:59 is quiet."""
    hour = moment.hour
    if quiet_start == quiet_end:
        return False
    if quiet_start < quiet_end:
        return quiet_start <= hour < quiet_end
    return hour >= quiet_start or hour < quiet_end


def next_send_time(moment, quiet_start, quiet_end):
    """The first moment at or after `moment` that is outside quiet hours."""
    if not in_quiet_hours(moment, quiet_start, quiet_end):
        return moment
    candidate = moment.replace(minute=0, second=0, microsecond=0)
    if candidate.hour >= quiet_end:
        candidate = candidate + timedelta(days=1)
    return candidate.replace(hour=quiet_end)


# --------------------------------------------------------------------------
# Segment estimation
# --------------------------------------------------------------------------

# The GSM-7 alphabet an SMS can use before the carrier falls back to UCS-2.
# This matters for money: GSM-7 fits 160 characters per segment, UCS-2 only 70,
# so one stray character in a translated template can more than double the cost
# of every message an agency sends.
GSM7 = set(
    "@\u00a3$\u00a5\u00e8\u00e9\u00f9\u00ec\u00f2\u00c7\n\u00d8\u00f8\r\u00c5\u00e5"
    "\u0394_\u03a6\u0393\u039b\u03a9\u03a0\u03a8\u03a3\u0398\u039e\u00c6\u00e6\u00df\u00c9"
    " !\"#\u00a4%&'()*+,-./0123456789:;<=>?"
    "\u00a1ABCDEFGHIJKLMNOPQRSTUVWXYZ\u00c4\u00d6\u00d1\u00dc\u00a7"
    "\u00bfabcdefghijklmnopqrstuvwxyz\u00e4\u00f6\u00f1\u00fc\u00e0"
)
GSM7_EXTENDED = set("^{}\\[~]|\u20ac")


def segment_info(body):
    """Character count, encoding, and segment count for an SMS body."""
    text = body or ""
    if all(ch in GSM7 or ch in GSM7_EXTENDED for ch in text):
        units = sum(2 if ch in GSM7_EXTENDED else 1 for ch in text)
        encoding, single, multi = "GSM-7", 160, 153
    else:
        units = len(text)
        encoding, single, multi = "UCS-2", 70, 67
    if units == 0:
        segments = 0
    elif units <= single:
        segments = 1
    else:
        segments = -(-units // multi)
    return {"characters": len(text), "units": units, "encoding": encoding,
            "segments": segments, "per_segment": single if segments <= 1 else multi}


def non_gsm_characters(body):
    """The specific characters that would force a template into UCS-2."""
    return sorted({ch for ch in (body or "")
                   if ch not in GSM7 and ch not in GSM7_EXTENDED})


# --------------------------------------------------------------------------
# Queue and dispatch
# --------------------------------------------------------------------------

class Blocked(Exception):
    """Raised when a message may not be queued for this contact."""


def reachability(contact):
    """Why a contact can or cannot be texted. Drives both the UI and the queue."""
    if not contact["phone"]:
        return False, "No mobile number on file"
    if contact["opted_out"]:
        return False, "Opted out of text messages"
    if not contact["consent_sms"]:
        return False, "No SMS consent recorded"
    if not contact["active"]:
        return False, "Contact is archived"
    return True, "Reachable"


def queue_message(conn, org, contact, body, language=None, template_code=None,
                  subject_type=None, subject_id=None, created_by=None, now=None):
    """Queue one outbound SMS. Returns the message id.

    Raises Blocked if the contact may not be texted -- callers should check
    reachability() first and present the reason rather than swallowing it.
    """
    ok, reason = reachability(contact)
    if not ok:
        raise Blocked(reason)

    moment = now or db.now()
    send_at = next_send_time(moment, org["quiet_start"], org["quiet_end"])
    status = "queued" if send_at <= moment else "held"

    cursor = conn.execute(
        """INSERT INTO messages
           (org_id, contact_id, direction, body, language, status, template_code,
            subject_type, subject_id, scheduled_for, created_by, created_at)
           VALUES (?, ?, 'out', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (org["id"], contact["id"], body, language or contact["preferred_language"],
         status, template_code, subject_type, subject_id,
         send_at.strftime("%Y-%m-%d %H:%M:%S"), created_by,
         moment.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    return cursor.lastrowid


def dispatch_due(conn, org_id=None, provider=None, now=None):
    """Send every queued/held message whose scheduled time has arrived.

    Returns (sent, failed). Safe to run repeatedly -- it only picks up messages
    still in a pending state.
    """
    provider = provider or get_provider()
    moment = now or db.now()
    stamp = moment.strftime("%Y-%m-%d %H:%M:%S")

    sql = ("""SELECT m.*, c.phone, o.sms_from, o.quiet_start, o.quiet_end
              FROM messages m
              JOIN contacts c ON c.id = m.contact_id
              JOIN organizations o ON o.id = m.org_id
              WHERE m.direction = 'out'
                AND m.status IN ('queued', 'held')
                AND (m.scheduled_for IS NULL OR m.scheduled_for <= ?)""")
    params = [stamp]
    if org_id:
        sql += " AND m.org_id = ?"
        params.append(org_id)

    sent = failed = 0
    for row in conn.execute(sql, params).fetchall():
        if in_quiet_hours(moment, row["quiet_start"], row["quiet_end"]):
            # Slipped into quiet hours while waiting; push to the next window.
            conn.execute(
                "UPDATE messages SET status = 'held', scheduled_for = ? WHERE id = ?",
                (next_send_time(moment, row["quiet_start"], row["quiet_end"]).strftime(
                    "%Y-%m-%d %H:%M:%S"), row["id"]))
            continue
        result = provider.send(row["phone"], row["body"], row["sms_from"])
        if result.ok:
            sent += 1
            conn.execute(
                "UPDATE messages SET status = 'sent', sent_at = ?, provider_ref = ?, error = NULL"
                " WHERE id = ?", (stamp, result.provider_ref, row["id"]))
        else:
            failed += 1
            conn.execute("UPDATE messages SET status = 'failed', error = ? WHERE id = ?",
                         (result.error, row["id"]))
    conn.commit()
    return sent, failed


# --------------------------------------------------------------------------
# Inbound
# --------------------------------------------------------------------------

def classify_inbound(body):
    """'stop', 'start', 'help', or 'reply' for an inbound message body."""
    word = re.sub(r"[^\w]", "", (body or "").strip().split(" ")[0]).lower()
    if word in STOP_WORDS:
        return "stop"
    if word in START_WORDS:
        return "start"
    if word in HELP_WORDS:
        return "help"
    return "reply"


def receive_inbound(conn, from_phone, body, now=None):
    """Record an inbound SMS and apply any opt-out/opt-in keyword.

    Returns (message_id, intent, contact_row) -- contact_row is None when the
    number matches nobody, in which case nothing is stored.
    """
    moment = now or db.now()
    stamp = moment.strftime("%Y-%m-%d %H:%M:%S")
    phone = normalize_phone(from_phone)
    contact = conn.execute(
        "SELECT * FROM contacts WHERE phone = ? ORDER BY id LIMIT 1", (phone,)).fetchone()
    if not contact:
        return None, "unknown", None

    intent = classify_inbound(body)
    cursor = conn.execute(
        """INSERT INTO messages
           (org_id, contact_id, direction, body, language, status, created_at, sent_at)
           VALUES (?, ?, 'in', ?, ?, 'received', ?, ?)""",
        (contact["org_id"], contact["id"], body or "", contact["preferred_language"],
         stamp, stamp))

    # STOP is a property of the phone, not of one case file. Households share
    # numbers, so the opt-out has to cover every contact reachable at it --
    # otherwise a participant who said stop keeps getting texts under a
    # relative's record.
    if intent == "stop":
        conn.execute("UPDATE contacts SET opted_out = 1, opted_out_at = ? WHERE phone = ?",
                     (stamp, phone))
        conn.execute(
            "UPDATE messages SET status = 'canceled' WHERE direction = 'out'"
            " AND status IN ('queued', 'held')"
            " AND contact_id IN (SELECT id FROM contacts WHERE phone = ?)", (phone,))
    elif intent == "start":
        conn.execute(
            "UPDATE contacts SET opted_out = 0, opted_out_at = NULL, consent_sms = 1,"
            " consent_at = COALESCE(consent_at, ?) WHERE phone = ?", (stamp, phone))

    conn.commit()
    contact = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact["id"],)).fetchone()
    return cursor.lastrowid, intent, contact
