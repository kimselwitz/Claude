# Onramp

A texting app for people whose problem is not typing.

## The premise

For a lot of neurodivergent people the hard part of texting isn't writing a
reply. It's the gap between *seeing* a message and *answering* it. Every hour in
that gap raises the price of the reply — now it needs an apology, and the apology
needs an explanation good enough to justify the delay — which widens the gap.
Left alone it ends in a thread nobody can face, and that's how people quietly
lose friends they actually like.

Every design decision in here follows from that one observation: **intervene
while the reply is still cheap, and never let a thread reach the point where
answering feels mortifying.**

## The four moves

**Read without owing.** Opening a message feels like signing for it, so the
triage screen decouples the two: you read the text and answer exactly one
question — does this need a reply at all? "No" is one tap and a legitimate
answer. Most messages are information, not requests.

**Buy time in one tap.** A holding reply ("saw this, brain's slow today, back to
you tonight") costs a second and does most of the work, because it converts
*they're ignoring me* into *they'll get to it* — which was the frightening part.
The app treats a sent holding reply as the thread being handled.

**Never start from blank.** Replies are assembled from sentences you've already
approved, kept in a library that reorders itself by what you actually use. The
blank box is where the paralysis lives. For threads that have gone cold there's a
no-grovel opener, because over-apologising is a large part of why late replies
never get sent — an apology opens a subject, and then you owe an essay.

**Cheapest first.** The deck sorts by how much effort a reply takes, not by
urgency. Urgency-sorting puts the hardest message on top, which is exactly where
avoidance starts. Momentum gets you to the hard one; dread doesn't.

## And some things it deliberately refuses to do

- **No red.** Not for lateness, not for errors. Alarm colouring on a backlog is
  what makes the backlog unapproachable.
- **No count badge anywhere in the chrome.** A number visible from every screen
  is a debt tally. (There's a test asserting the nav contains no digits.)
- **No streaks.** A broken streak during a bad week is a reason to delete the app.
- **It never says "overdue."** Threads are "still easy", "still warm", "cooling
  off", "gone cold". Time is in plain language — "since Tuesday", not "4d".
- **Nothing auto-sends.**
- **Every screen has an exit that isn't "reply now."** Built for demand avoidance
  as much as anxiety: an app that tells you to reply is an app that makes
  replying harder.

## Screens

| Screen | What it's for |
|---|---|
| **Now** | The deck. What's owed, cheapest first, with a reply window timer. |
| **Unopened** | Read-without-owing triage. One question, three answers. |
| **Thread** | Conversation plus the reply scaffold: buy time, assemble, or type. |
| **Scripts** | Your phrase library, sorted by what you actually use. |
| **People** | Felt stakes vs. observed patience, side by side. |
| **Amnesty** | Clears the cold pile in one honest message. |
| **Proof** | After a late reply: did it actually go badly? |

### Two of those deserve more explanation

**People** stores two separate columns: how much it *feels* like is riding on
replying, and how the person has *actually* reacted to a slow reply. Texting
anxiety fuses these. Keeping them apart, and showing them next to each other, is
the point — when a thread is from someone marked high-stakes *and* genuinely
patient, the deck says so outright: "feels big · actually isn't."

**Proof** is the only screen that can change the belief underneath the anxiety.
After a reply sent more than two days late, the app asks once whether it went
badly, and keeps the tally. For most people it reads *n went fine, 0 went badly*
within a couple of weeks, which is a harder thing to argue with than
reassurance.

**Amnesty** exists because past a certain age a message stops being a task and
becomes a monument. People abandon entire friendships rather than climb one. It
sends one honest line to every cold thread at once, with no explanation of where
you went — explanations invite follow-up questions, which is the reason these
messages never get sent.

## Running it

```bash
pip install -r requirements.txt
python seed.py     # creates onramp.db with a realistic backlog to poke at
python app.py      # http://127.0.0.1:5000
```

Flask + SQLite, no build step, no network calls, no accounts. Single user by
design — a login screen is friction in front of the exact task you're already
avoiding. Mobile-first layout; dark mode and `prefers-reduced-motion` are
honoured.

The seed data is shaped like a real bad week on purpose: a couple of things from
this morning that are still cheap, some three-day-olds sitting in the worst zone,
and two that have gone properly cold — because the cold ones are what the app is
actually for.

## Where the real messages would come from

This is a working prototype of the *mechanics*, running on its own database. It
demonstrates the interaction model end to end; it is not yet plugged into a
messaging service. That last step is worth being honest about, because it's the
part that constrains the product:

- **Android** can do the real thing. An app can hold the `SMS_DELIVER` role and
  become the default SMS handler, which means true triage before a notification
  ever lands.
- **iOS cannot.** Third-party apps have no read access to Messages, and there's
  no path around that. The realistic iOS versions are (a) a Share Sheet
  extension, so you push a message into Onramp from Messages when you feel the
  freeze, or (b) an SMS filter extension, which sees messages only from unknown
  senders. Both are meaningfully weaker than the Android version.
- **Platforms with APIs** — Slack, Discord, WhatsApp Business, email — can be
  wired up properly and are where the model would work best without OS fights.
- **Or no integration at all.** Onramp works as a companion you keep beside your
  actual messages: you log the thread, and it handles the deciding. Weaker, but
  it ships everywhere and it still moves the part that's hard, which is the
  deciding rather than the sending.

The read-receipt promise on the triage screen is honest only on the Android
build. On any other platform that line should be removed rather than softened.

## Layout

```
app.py          routes, plus the reply-scaffolding logic
models.py       sqlite3 models; the temperature bands and plain-language clock
seed.py         schema + a realistic backlog
static/         one stylesheet, with the sensory rules written down in it
templates/      one per screen
```

## Tests

```bash
python test_onramp.py
```

56 assertions covering every route and state transition, plus guards on two design
rules that are easy to break by accident later: the nav must contain no digits,
and no screen may use alarm or streak language.
