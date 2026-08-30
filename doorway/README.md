# Doorway

Participant communication and document chasing for housing programs — in the
participant's own language.

Doorway sits **alongside** an agency's system of record, never replacing it. It
answers one question well: *what are we still waiting on, from whom, and has
anybody actually told them?*

## Why this and not "PHA software"

This is wedge #1 from the PHA software market assessment. The core
housing-management market — the system that holds the 50058, submits to HUD, and
calculates rent — is closed to a small team: MRI (~35% of PHAs after rolling up
Tenmast, HAB, and HAPPY), Yardi, and Constellation's Emphasys own it, and the
compliance treadmill (HIP/HOTMA, NSPIRE, FedRAMP-grade PII) is a full-time
engineering-plus-compliance operation on its own.

Document chasing is the opposite: highest pain, lowest compliance, a metric the
buyer already tracks, and no need to hold anyone's income data. It sells first to
nonprofit housing counseling agencies, CoC/homeless-service providers, and TBRA
programs — buyers who sign without a HUD procurement handbook — and then to small
PHAs alongside whatever system of record they already run.

**The boundary is load-bearing.** Doorway stores contact details, document
status, and message history. It stores no income, assets, household
composition, or SSNs, and it never submits anything to HUD. The moment a feature
requires reading or writing the 50058, it is out of scope — that is the trap the
research warned about, and `db.py` says so at the top of the schema.

## What it does

- **Document requests** — request a stack of documents from a participant in one
  pass, each tracked separately with its own due date and status.
- **Text messages in seven languages** — English, Spanish, French, Portuguese,
  Somali, Arabic, and Lingala. Every template holds one body per language;
  document names are translated too, so a Spanish message doesn't ask for
  "Proof of income."
- **Automatic reminders** — rules fire relative to a due date (3 days before, on
  the day, 2 and 7 days after). Each rule fires at most once per request.
- **Consent and opt-out** — nothing is sent without recorded SMS consent. STOP
  (and *alto*, *arrêt*, *joogso*, *pare*) opts out everyone at that number and
  cancels their queued messages.
- **Quiet hours** — messages created overnight are held and released in the
  morning. No participant is woken at 11pm by an automated nudge.
- **Cost visibility** — the template editor shows character count, GSM-7 vs
  UCS-2 encoding, and segment count, so an agency can see when an accented
  character doubles the cost of a message.
- **Metrics that renew a pilot** — past due, median days to receipt, reply rate,
  and what share of the caseload is reachable at all.

## Running it

Python 3.9+ and two packages.

```bash
cd doorway
pip install -r requirements.txt

# Starter templates, document list, and reminder rules:
python init_db.py --org "Your Agency" --username you

# Or with a demo caseload to click through:
python init_db.py --demo --username you --password changeme --force

python app.py      # http://localhost:5000
```

Reminders run on a schedule, not on someone remembering:

```bash
0 9 * * *  cd /srv/doorway && python jobs.py run --org 1
```

`python jobs.py nudges --dry-run` prints exactly what would go out, in each
participant's language, without sending anything.

## Sending real texts

Out of the box the `console` provider writes messages to the log instead of a
carrier — full consent, quiet-hours, and queue behaviour, nothing leaving the
building. That is the right setting for a demo or a dry run with a design
partner.

To go live:

```bash
export DOORWAY_SMS_PROVIDER=twilio
export TWILIO_ACCOUNT_SID=... TWILIO_AUTH_TOKEN=... TWILIO_FROM=+12075550100
```

Point the carrier's inbound webhook at `POST /sms/inbound`. Before real numbers
are involved, put that route behind the provider's signature validation — it is
deliberately unauthenticated at the app layer.

## Before a real pilot

Doorway is a working product, not a hardened one. Things a first paying agency
needs that are not here yet:

- **Signature validation on the inbound webhook** (see above).
- **Reviewed translations.** The shipped text is starter text. Language access
  is a legal obligation under HUD LEP guidance — have the agency's own
  interpreter review each variant in the template editor.
- **Transport security and backups.** Run behind HTTPS; the SQLite file holds
  names, numbers, and message history.
- **A real WSGI server** — `app.py` runs Flask's development server.
- **Per-user accounts.** `init_db.py` creates one admin;
  `models.create_user()` adds more.

## Tests

```bash
python -m unittest discover -s tests -v
```

36 tests covering phone normalization, quiet hours, consent gates, opt-out
propagation across shared household numbers, template fallback, reminder
idempotency, metrics, and every page rendering.

## Layout

| File | What lives there |
| --- | --- |
| `db.py` | Schema and connection. The scope boundary is documented here. |
| `models.py` | Every query that touches participant data. |
| `messaging.py` | Rendering, consent, quiet hours, providers, inbound keywords. |
| `nudges.py` | The reminder engine and its pluggable subject registry. |
| `languages.py` | Supported languages. |
| `app.py` | Flask routes and forms. |
| `jobs.py` | Cron entry point. |
| `seed.py` | Starter templates, document types, rules, demo caseload. |

See `ROADMAP.md` for iterations 2 and 3.
