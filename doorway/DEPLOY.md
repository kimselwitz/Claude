# Deploying Doorway to Railway

Doorway is a Flask app on SQLite. It needs a **persistent disk** — which is why
Railway (persistent volumes) rather than Vercel (serverless, ephemeral
filesystem, where every participant record would vanish between requests).

Everything below is one Railway project with two services.

---

## 1. Web service

**New Project → Deploy from GitHub repo →** `kimselwitz/Claude`.

In **Settings**:

| Setting | Value |
| --- | --- |
| Root Directory | `doorway` |
| Start Command | picked up from `railway.json` / `Procfile` |

Add a **Volume** mounted at `/data`. This is the only copy of your data.

### Variables

```
DOORWAY_ENV=production
DOORWAY_SECRET_KEY=<paste a generated key>
DOORWAY_DB=/data/doorway.db
DOORWAY_JOB_TOKEN=<paste a second generated key>

# Read once, on first boot only, to create the agency and first admin:
DOORWAY_ORG_NAME=Your Agency
DOORWAY_ADMIN_USERNAME=you
DOORWAY_ADMIN_PASSWORD=<a real password>
```

Generate each key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`DOORWAY_SECRET_KEY` is mandatory in production — the app refuses to start
without it rather than falling back to a known development key.

On first boot `wsgi.py` creates the schema, the starter document list, the
templates in all seven languages, the four reminder rules, and your admin
account. **On every later deploy it does nothing** — your data is left alone.
Change the admin password from inside the app afterwards, then clear
`DOORWAY_ADMIN_PASSWORD` from the variables.

---

## 2. Cron service (reminders)

Reminders have to run on a schedule or the product does nothing between logins.

A Railway volume attaches to exactly **one** service, so a second service can't
open the same SQLite file. Instead the cron service calls the web service over
HTTP:

**New Service → Empty Service**, in the same project:

| Setting | Value |
| --- | --- |
| Start Command | `curl -fsS -X POST -H "X-Doorway-Job-Token: $DOORWAY_JOB_TOKEN" $DOORWAY_URL/jobs/run` |
| Cron Schedule | `0 13 * * *` |

Variables: `DOORWAY_JOB_TOKEN` (identical to the web service's) and
`DOORWAY_URL` (your web service's public URL).

`0 13 * * *` is **13:00 UTC = 9am Eastern Daylight Time**. Railway cron is UTC
and does not follow daylight saving, so this drifts to 8am when Maine returns to
EST in November — change it to `0 14 * * *` then, or accept the hour.

The endpoint returns JSON showing what was queued, sent, and skipped per agency,
so the cron log tells you what happened. It 404s when `DOORWAY_JOB_TOKEN` is
unset and 403s on a bad token.

---

## 3. Text messaging

Until these are set, Doorway uses the `console` provider: messages travel the
full consent / quiet-hours / queue path and land in the message log, but nothing
reaches a carrier. That is the correct setting for a design-partner demo.

To send real texts, add to the web service:

```
DOORWAY_SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM=+1207XXXXXXX
```

Then point the Twilio number's inbound webhook at:

```
https://<your-app>.up.railway.app/sms/inbound
```

**Before real numbers are involved,** put that route behind Twilio's request
signature validation. It is deliberately unauthenticated at the app layer, which
is fine for the console provider and not fine once a public URL accepts inbound
messages that can opt participants out.

---

## 4. Backups

The volume is the only copy. Railway does not back up volumes for you.

```bash
railway run sqlite3 /data/doorway.db ".backup '/data/backup-$(date +%F).db'"
```

Run it on a schedule, and pull a copy off the platform periodically. This file
holds names, phone numbers, and message history for real households.

---

## Still open before a live pilot

- Twilio signature validation on `/sms/inbound` (above).
- Interpreter review of all seven language variants in the template editor —
  the shipped text is starter text, and language access is a legal obligation.
- More staff accounts: `models.create_user()`; there is no invite UI yet.
- SQLite is right for one agency at pilot scale. Multiple agencies at volume is
  the point to move to Postgres — `models.py` is the only file with SQL in it.
