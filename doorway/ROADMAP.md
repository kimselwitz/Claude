# Roadmap

Doorway is built as the first of three wedges from the PHA software market
assessment. Iteration 1 is shipped; iterations 2 and 3 reuse its machinery
rather than sitting beside it.

---

## Iteration 1 — Applicant/participant communication + document chasing *(shipped)*

Wedge #1: highest pain, lowest compliance, clear ROI, no need to be the system
of record. Sold first to nonprofits, CoCs, and TBRA programs; then to small PHAs
alongside their existing system.

Everything the next two iterations need already exists here: contacts with
consent and language, translated templates, a queue with quiet hours, an
outbound/inbound message log, a rule engine, and a metrics page.

---

## Iteration 2 — Briefing/inspection scheduling with no-show reduction

Wedge #2. Voucher briefings and inspection appointments are high-volume,
high-no-show events with no dominant point solution. The metric sells itself:
an agency knows its no-show rate, and can see it move.

**What gets built**

- `appointments` table: contact, kind (briefing / inspection / recert
  interview), starts_at, location, staff, status (scheduled / confirmed /
  attended / no-show / rescheduled).
- Slot management: staff define recurring briefing sessions with a capacity;
  participants are assigned or self-select.
- Confirm-by-reply: an inbound `YES` / `SI` / `HAA` on a reminder marks the
  appointment confirmed; anything else routes to staff.
- A no-show dashboard: rate by appointment kind, by language, by lead time —
  the number a pilot renews on.

**What it reuses, unchanged**

The subject registry in `nudges.py` is the seam. Iteration 1 registers
`DocumentRequestSubject`; iteration 2 registers an `AppointmentSubject` with the
same two methods (`pending()` and `context()`), and inherits rule matching,
one-fire-per-subject, language selection, the consent gate, quiet hours, and
dispatch. The `messages` table already carries `subject_type`/`subject_id`, so
appointment reminders thread into the same participant history with no
migration. Templates already have a `category` column; appointment templates
just use a different value.

New code is roughly: one table, one subject class, one confirm-keyword branch in
`classify_inbound()`, and the scheduling UI.

**Sequencing note.** Ship this only once iteration 1 has a paying design
partner. Scheduling is a bigger build with a harder demo, and the research is
explicit that the fastest validation path is the communication wedge first.

---

## Iteration 3 — Landlord recruitment and retention CRM

Wedge #3. Voucher lease-up succeeded only 57% of the time in 2022 (down from 66%
in 2020), with a median successful search of 78 days — a proven, funded pain
(Padmission, Housing Connector, PadSplit), still fragmented enough for a
regionally-focused entrant.

**What gets built**

- Landlord pipeline: prospect → contacted → interested → onboarded → active
  → churned, with owner assignment and follow-up dates.
- Unit availability: bedrooms, rent, accessibility, neighborhood, voucher
  acceptance — matched against participants' search criteria.
- Navigator view: which participants are searching, how long, which landlords
  they have been referred to, and what came back.
- Retention: damage-claim and incentive tracking; a "landlord left the program"
  alert with a reason code.

**What it reuses, unchanged**

`contacts.contact_type` already exists and already defaults to `participant`.
Landlords are contacts with `contact_type = 'landlord'` — so consent, opt-out,
preferred language, phone normalization, the message queue, quiet hours, and the
full message history work on day one. `models.list_contacts()` already takes a
`contact_type` argument. Landlord outreach templates use the `landlord`
template category.

New code is roughly: the pipeline and units tables, the matching view, and a
landlord-side UI. None of the messaging layer is touched.

---

## Cross-cutting, whenever the business needs it

- **Price under the micro-purchase threshold.** The research is specific: a
  sympathetic PHA can buy below micro-purchase with minimal process, and between
  micro and the $350K simplified-acquisition threshold with small-purchase
  quotes. Design pricing so the first PHA never needs an RFP or a board fight.
- **SOC 2.** A practical baseline for government sales, achievable for a small
  vendor over time. FedRAMP is not — which is the other reason never to hold
  the 50058 data of record.
- **Read-only imports.** Participants and due dates can be imported from a CSV
  export of the system of record. One-way, always: any feature that writes back
  to the 50058 is out of scope, permanently.
- **Multi-agency.** The schema is already scoped by `org_id` throughout. Adding
  agency switching and per-agency billing is UI and auth work, not a redesign.
