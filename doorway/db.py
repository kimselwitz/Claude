"""
Database schema and connection handling for Doorway.

Scope boundary (deliberate, see ROADMAP.md):
Doorway is NOT a system of record. It stores only what is needed to contact a
participant and to track which documents an agency is waiting on. There are no
columns here for income, assets, SSN, household composition, rent calculation,
or anything else that appears on form HUD-50058 -- holding that data would drag
the product into HUD certification, HIP submission, and FedRAMP-grade
obligations that a small vendor cannot carry. Keep it that way.
"""
import os
import sqlite3
from datetime import datetime

DEFAULT_DB_PATH = os.environ.get("DOORWAY_DB", "doorway.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS organizations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'nonprofit',
    timezone        TEXT NOT NULL DEFAULT 'America/New_York',
    quiet_start     INTEGER NOT NULL DEFAULT 21,
    quiet_end       INTEGER NOT NULL DEFAULT 8,
    sms_from        TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id          INTEGER NOT NULL,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'staff',
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (org_id) REFERENCES organizations(id)
);

-- Contacts are typed so that iteration 3 (landlord recruitment CRM) can reuse
-- the same messaging, consent, and language machinery without a data migration.
-- Iteration 1 only creates and lists contacts of type 'participant'.
CREATE TABLE IF NOT EXISTS contacts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id              INTEGER NOT NULL,
    contact_type        TEXT NOT NULL DEFAULT 'participant',
    external_ref        TEXT,
    first_name          TEXT NOT NULL,
    last_name           TEXT NOT NULL,
    phone               TEXT,
    email               TEXT,
    preferred_language  TEXT NOT NULL DEFAULT 'en',
    program             TEXT,
    consent_sms         INTEGER NOT NULL DEFAULT 0,
    consent_at          TIMESTAMP,
    opted_out           INTEGER NOT NULL DEFAULT 0,
    opted_out_at        TIMESTAMP,
    notes               TEXT,
    active              INTEGER NOT NULL DEFAULT 1,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (org_id) REFERENCES organizations(id)
);

CREATE INDEX IF NOT EXISTS idx_contacts_org  ON contacts(org_id, contact_type, active);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);

CREATE TABLE IF NOT EXISTS document_types (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id          INTEGER NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (org_id) REFERENCES organizations(id)
);

-- A translated message that names the document in English is only half
-- translated, so document names carry their own per-language text.
CREATE TABLE IF NOT EXISTS document_type_names (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_type_id    INTEGER NOT NULL,
    language            TEXT NOT NULL,
    name                TEXT NOT NULL,
    UNIQUE (document_type_id, language),
    FOREIGN KEY (document_type_id) REFERENCES document_types(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS document_requests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id              INTEGER NOT NULL,
    contact_id          INTEGER NOT NULL,
    document_type_id    INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'open',
    due_date            DATE NOT NULL,
    requested_by        INTEGER,
    requested_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at           TIMESTAMP,
    notes               TEXT,
    FOREIGN KEY (org_id) REFERENCES organizations(id),
    FOREIGN KEY (contact_id) REFERENCES contacts(id),
    FOREIGN KEY (document_type_id) REFERENCES document_types(id),
    FOREIGN KEY (requested_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_requests_open ON document_requests(org_id, status, due_date);

CREATE TABLE IF NOT EXISTS message_templates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id          INTEGER NOT NULL,
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'document_request',
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (org_id, code),
    FOREIGN KEY (org_id) REFERENCES organizations(id)
);

CREATE TABLE IF NOT EXISTS template_variants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id     INTEGER NOT NULL,
    language        TEXT NOT NULL,
    body            TEXT NOT NULL,
    UNIQUE (template_id, language),
    FOREIGN KEY (template_id) REFERENCES message_templates(id) ON DELETE CASCADE
);

-- subject_type/subject_id point at whatever the message is about. Iteration 1
-- ships 'document_request'; iteration 2 adds 'appointment' with no schema change.
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id          INTEGER NOT NULL,
    contact_id      INTEGER NOT NULL,
    direction       TEXT NOT NULL,
    body            TEXT NOT NULL,
    language        TEXT NOT NULL DEFAULT 'en',
    status          TEXT NOT NULL DEFAULT 'queued',
    template_code   TEXT,
    subject_type    TEXT,
    subject_id      INTEGER,
    scheduled_for   TIMESTAMP,
    sent_at         TIMESTAMP,
    provider_ref    TEXT,
    error           TEXT,
    created_by      INTEGER,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (org_id) REFERENCES organizations(id),
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_contact ON messages(contact_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_pending ON messages(status, scheduled_for);

CREATE TABLE IF NOT EXISTS nudge_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id          INTEGER NOT NULL,
    name            TEXT NOT NULL,
    subject_type    TEXT NOT NULL DEFAULT 'document_request',
    template_code   TEXT NOT NULL,
    offset_days     INTEGER NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (org_id) REFERENCES organizations(id)
);

-- One row per (rule, subject) so a rule never fires twice for the same item.
CREATE TABLE IF NOT EXISTS nudge_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id         INTEGER NOT NULL,
    subject_type    TEXT NOT NULL,
    subject_id      INTEGER NOT NULL,
    message_id      INTEGER,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (rule_id, subject_type, subject_id),
    FOREIGN KEY (rule_id) REFERENCES nudge_rules(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id          INTEGER NOT NULL,
    user_id         INTEGER,
    action          TEXT NOT NULL,
    detail          TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(db_path=None):
    """Open a connection with row access by name and foreign keys enforced.

    WAL mode and a busy timeout matter once the app runs under more than one
    gunicorn worker: readers stop blocking the writer, and a worker that finds
    the database briefly locked waits instead of raising.
    """
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def now():
    """Single source of 'now' so tests can reason about timestamps."""
    return datetime.now().replace(microsecond=0)


def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")
