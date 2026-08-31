"""
Create the database and fill it with a realistic day's backlog.

The demo data is deliberately shaped like a real bad week: a couple of things
from this morning that are still cheap, some three-day-old ones sitting in the
worst zone, and two that have gone properly cold - because the cold ones are
what the app is really for.
"""
from datetime import datetime, timedelta
from models import Database, Person, Thread, Script, ISO

db = Database()
person_model = Person(db)
thread_model = Thread(db)
script_model = Script(db)


def ago(hours=0, days=0):
    return (datetime.now() - timedelta(hours=hours, days=days)).strftime(ISO)


BUILTIN_SCRIPTS = [
    # Holding replies - the highest-leverage thing in the app.
    ("holding", "Saw this — my brain's slow today. Coming back to it properly tonight."),
    ("holding", "Got it! Give me a day, I want to answer this properly."),
    ("holding", "👀 reading this, just low on words right now. Not ignoring you."),
    ("holding", "Yes to this in principle — details when I've got a spare brain cell."),

    # Openers - so the box is never blank.
    ("opener", "Hey!"),
    ("opener", "Ok so —"),
    ("opener", "Sorry for the lag!"),
    ("opener", "Hey — late reply, no drama, just slow with my phone. Anyway:"),

    # Middles - the boring content of most replies.
    ("middle", "That works for me."),
    ("middle", "I can't do that day, but I could do the weekend after."),
    ("middle", "I'd love to but I'm at capacity this week."),
    ("middle", "Congratulations, genuinely — that's brilliant news."),
    ("middle", "Ah I'm sorry, that sounds properly rough."),
    ("middle", "Can you send me the details and I'll look tonight?"),

    # Closers - so you don't trail off and abandon a half-written message.
    ("closer", "Hope you're doing ok x"),
    ("closer", "Talk soon!"),
    ("closer", "No rush on replying to this either."),

    # Declines - no, without a paragraph of justification attached.
    ("decline", "Can't make it this time, but have a great one!"),
    ("decline", "I'm going to sit this one out — not up to it this week."),
    ("decline", "That's a no from me, sorry! Next time."),
]

PEOPLE = [
    # (name, relationship, stakes, patience, holding_ok, notes)
    ("Maya", "friend since school", "high", "fine", 1,
     "Has literally said 'reply whenever, I know how you are.' Believe her."),
    ("Dad", "dad", "high", "notices", 1,
     "Sends five texts in a row. Only ever needs one answer back."),
    ("Ruth", "manager", "high", "notices", 1,
     "Work hours only. A holding reply is normal and expected here."),
    ("Sam", "flatmate", "low", "fine", 1, ""),
    ("Priya", "friend", "medium", "fine", 1,
     "Also hates the phone. You have talked about this."),
    ("Aunt Cath", "aunt", "medium", "unknown", 0,
     "Prefers a proper answer to a quick one. No holding replies."),
    ("Theo", "friend of a friend", "low", "unknown", 1, ""),
]

# (person index, state, effort, reply_needed, [(direction, body, age-kwargs)])
THREADS = [
    (3, "waiting", "tiny", "yes", [
        ("in", "are we out of washing up liquid or is it hiding", dict(hours=2)),
    ]),
    (4, "unopened", None, None, [
        ("in", "saw a dog today that looked exactly like your old one, thought of you 🐕",
         dict(hours=4)),
    ]),
    (2, "waiting", "small", "yes", [
        ("in", "Can you send over the Q3 numbers when you get a sec? No huge rush, "
               "just want them before Thursday.", dict(hours=20)),
    ]),
    (1, "unopened", None, None, [
        ("in", "Hello love", dict(days=1, hours=3)),
        ("in", "Just checking in", dict(days=1, hours=3)),
        ("in", "No need to ring, only if you want to", dict(days=1, hours=2)),
    ]),
    (0, "waiting", "real", "yes", [
        ("in", "Ok so the wedding is definitely the 14th — are you coming?? "
               "Need to tell them numbers by end of month. Also would you be up for "
               "doing a reading, no pressure at all if not", dict(days=3)),
    ]),
    (6, "unopened", None, None, [
        ("in", "hey! Jonah gave me your number — a few of us are doing a thing "
               "on Saturday if you fancy it", dict(days=4)),
    ]),
    (5, "waiting", "real", "yes", [
        ("in", "Just wondered how you got on at the appointment. Thinking of you. "
               "Ring me any time.", dict(days=9)),
    ]),
    (4, "holding_sent", "small", "yes", [
        ("in", "Are you still up for the thing next month? Need to book", dict(days=12)),
        ("out", "Got it! Give me a day, I want to answer this properly.", dict(days=11)),
    ]),
    (0, "waiting", "small", "yes", [
        ("in", "how did the interview go?!", dict(days=23)),
    ]),
]


def run():
    db.init_db()

    conn = db.get_connection()
    already = conn.execute("SELECT COUNT(*) c FROM people").fetchone()["c"]
    conn.close()
    if already:
        print("Database already has data. Delete onramp.db first to reseed.")
        return

    for slot, text in BUILTIN_SCRIPTS:
        script_model.add(slot, text)

    person_ids = [person_model.create(*p) for p in PEOPLE]

    for person_idx, state, effort, reply_needed, msgs in THREADS:
        tid = thread_model.create(person_ids[person_idx], state=state)
        for direction, body, when in msgs:
            thread_model.add_message(tid, direction, body,
                                     kind="holding" if direction == "out" else "normal",
                                     sent_at=ago(**when))
        if state != "unopened":
            conn = db.get_connection()
            conn.execute(
                "UPDATE threads SET effort = ?, reply_needed = ?, opened_at = ? WHERE id = ?",
                (effort, reply_needed, ago(hours=1), tid))
            conn.commit()
            conn.close()

    print(f"Seeded {len(person_ids)} people, {len(THREADS)} threads, "
          f"{len(BUILTIN_SCRIPTS)} scripts.")


if __name__ == "__main__":
    run()
