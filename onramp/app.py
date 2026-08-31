"""
Onramp - a texting app for people whose problem is not typing.

The premise: for a lot of neurodivergent people the hard part of texting is not
composing a reply, it is the gap between "I saw it" and "I answered it." Every
hour in that gap raises the cost of the reply, which widens the gap. Onramp is
built to keep that gap short and cheap, and to make sure no thread ever reaches
the point where replying feels mortifying.

Rules the whole app obeys:
  - Nothing is ever red, overdue, or a streak. No counters on the nav.
  - Every screen offers at least one exit that is not "reply now."
  - Reading a message never commits you to answering it.
  - A one-line holding reply counts as handling it.
"""
from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import (Database, Person, Thread, Script, Window, Outcome,
                    TEMPERATURE_WORDS, now_str, parse)
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'onramp-local-single-user-key-change-in-production'

db = Database()
person_model = Person(db)
thread_model = Thread(db)
script_model = Script(db)
window_model = Window(db)
outcome_model = Outcome(db)


@app.context_processor
def inject_globals():
    """Deliberately does NOT expose an unread count. A number in the chrome of
    every screen is a badge, and a badge is the thing being avoided."""
    return {
        "active_window": window_model.active(),
        "temp_words": TEMPERATURE_WORDS,
    }


# ---------------------------------------------------------------- home / deck

@app.route('/')
def now():
    """The deck: what is actually owed, cheapest first."""
    unopened = thread_model.unopened()
    open_threads = thread_model.open_threads()
    snoozed = [t for t in thread_model.open_threads(include_snoozed=True) if t["is_snoozed"]]

    easy = [t for t in open_threads if t["temperature"] == "easy"]
    cold = [t for t in open_threads if t["temperature"] == "cold"]

    return render_template(
        'now.html',
        unopened=unopened,
        open_threads=open_threads,
        snoozed=snoozed,
        easy_count=len(easy),
        cold_count=len(cold),
        greeting=greeting(),
    )


def greeting() -> str:
    hour = datetime.now().hour
    if hour < 5:
        return "It's late. This can wait for morning."
    if hour < 12:
        return "Morning."
    if hour < 18:
        return "Afternoon."
    return "Evening."


# ------------------------------------------------------------------- triage

@app.route('/triage')
def triage():
    """Read without owing.

    The trap this screen exists to break: opening a message feels like signing
    for it. So here you read the text and answer exactly one question - does
    this need a reply at all - and "no" is a first-class, one-tap answer.
    """
    queue = thread_model.unopened()
    current = queue[0] if queue else None
    preview = thread_model.messages(current["id"]) if current else []
    return render_template('triage.html', current=current, preview=preview,
                           remaining=len(queue))


@app.route('/triage/<int:thread_id>', methods=['POST'])
def triage_decide(thread_id):
    reply_needed = request.form.get('reply_needed', 'yes')
    effort = request.form.get('effort', 'small')
    thread_model.triage(thread_id, reply_needed, effort)
    if reply_needed == 'no':
        flash("Closed. You didn't owe that one.", 'calm')
    return redirect(url_for('triage'))


# ------------------------------------------------------------------- threads

@app.route('/thread/<int:thread_id>')
def thread(thread_id):
    t = thread_model.get(thread_id)
    if not t:
        flash("That thread is gone.", 'calm')
        return redirect(url_for('now'))
    thread_model.mark_opened(thread_id)
    t = thread_model.get(thread_id)

    return render_template(
        'thread.html',
        t=t,
        messages=thread_model.messages(thread_id),
        holdings=script_model.by_slot('holding'),
        openers=script_model.by_slot('opener'),
        middles=script_model.by_slot('middle'),
        closers=script_model.by_slot('closer'),
        declines=script_model.by_slot('decline'),
        late_opener=late_opener(t),
    )


def late_opener(t) -> str:
    """A no-grovel opener for a late reply.

    Over-apologising is a large part of why late replies never get sent: the
    apology needs an explanation, the explanation needs to be good enough, and
    that is a whole essay standing between you and 'hey'. So the app supplies a
    short one that closes the subject instead of opening it.
    """
    if t["temperature"] == "cold":
        return "Hey - late reply, no drama, just slow with my phone. Anyway:"
    if t["temperature"] == "cooling":
        return "Sorry for the lag! Been a week. Anyway:"
    return ""


@app.route('/thread/<int:thread_id>/holding', methods=['POST'])
def send_holding(thread_id):
    """One tap, sends now.

    A holding reply is the highest-leverage thing in the app: it costs a second,
    it stops the clock socially, and it converts 'I owe you a whole answer' into
    'they know I saw it', which is most of the dread.
    """
    body = request.form.get('body', '').strip()
    if not body:
        flash("Nothing to send.", 'calm')
        return redirect(url_for('thread', thread_id=thread_id))
    thread_model.add_message(thread_id, 'out', body, kind='holding')
    thread_model.set_state(thread_id, 'holding_sent')
    script_model.used(body)
    window_model.touch()
    flash("Holding reply sent. That counts - the thread is handled for now.", 'good')
    return redirect(url_for('now'))


@app.route('/thread/<int:thread_id>/reply', methods=['POST'])
def send_reply(thread_id):
    body = request.form.get('body', '').strip()
    if not body:
        flash("Empty reply, nothing sent.", 'calm')
        return redirect(url_for('thread', thread_id=thread_id))
    t = thread_model.get(thread_id)
    thread_model.add_message(thread_id, 'out', body)
    thread_model.set_state(thread_id, 'answered')
    window_model.touch()
    for part in request.form.getlist('used_script'):
        script_model.used(part)
    if t and t["age_hours"] >= 48:
        session['ask_outcome'] = thread_id
    flash("Sent. Done with that one.", 'good')
    return redirect(url_for('now'))


@app.route('/thread/<int:thread_id>/no-reply', methods=['POST'])
def no_reply(thread_id):
    thread_model.set_state(thread_id, 'no_reply_needed')
    flash("Closed without replying. That was allowed.", 'calm')
    return redirect(url_for('now'))


@app.route('/thread/<int:thread_id>/snooze', methods=['POST'])
def snooze(thread_id):
    hours = int(request.form.get('hours', 6))
    thread_model.snooze(thread_id, hours)
    t = thread_model.get(thread_id)
    flash(f"Hidden until {t['snooze_words']}.", 'calm')
    return redirect(url_for('now'))


@app.route('/thread/<int:thread_id>/reopen', methods=['POST'])
def reopen(thread_id):
    thread_model.unsnooze(thread_id)
    thread_model.set_state(thread_id, 'waiting')
    flash("Back on the deck.", 'calm')
    return redirect(request.referrer or url_for('now'))


@app.route('/thread/<int:thread_id>/outcome', methods=['POST'])
def log_outcome(thread_id):
    """The evidence log. Answering 'did it actually go badly' after a late reply
    is the only thing in here that changes the belief underneath the anxiety."""
    went_badly = request.form.get('went_badly') == 'yes'
    t = thread_model.get(thread_id)
    days = int((t["age_hours"] // 24)) if t else 0
    outcome_model.log(thread_id, days, went_badly, request.form.get('note', ''))
    session.pop('ask_outcome', None)
    flash("Logged.", 'calm')
    return redirect(url_for('proof'))


@app.route('/outcome/skip', methods=['POST'])
def skip_outcome():
    session.pop('ask_outcome', None)
    return redirect(url_for('now'))


# -------------------------------------------------------------- reply window

@app.route('/window/start', methods=['POST'])
def start_window():
    """A reply window is a container. Texting with no edges expands to fill the
    whole day as low-grade dread; ten minutes with a defined end does not."""
    window_model.start(int(request.form.get('minutes', 10)))
    return redirect(url_for('now'))


@app.route('/window/end', methods=['POST'])
def end_window():
    w = window_model.active()
    window_model.end_all()
    touched = w["threads_touched"] if w else 0
    if touched:
        flash(f"Window closed. {touched} handled. Phone down.", 'good')
    else:
        flash("Window closed. Opening it at all was the hard part.", 'good')
    return redirect(url_for('now'))


# ------------------------------------------------------------------- scripts

@app.route('/scripts')
def scripts():
    return render_template('scripts.html', grouped=script_model.all_grouped(),
                           slot_labels=SLOT_LABELS)


SLOT_LABELS = {
    "holding": ("Holding replies", "Buys time and stops the clock. One tap, sends immediately."),
    "opener":  ("Openers", "The first line, so the box is never blank."),
    "middle":  ("Middles", "The actual content, for the common cases."),
    "closer":  ("Closers", "Ends the message so you don't trail off and abandon it."),
    "decline": ("Declines", "No, without a paragraph of justification."),
}


@app.route('/scripts/add', methods=['POST'])
def add_script():
    text = request.form.get('text', '').strip()
    slot = request.form.get('slot', 'middle')
    if text:
        script_model.add(slot, text)
        flash("Saved. It'll be there next time.", 'good')
    return redirect(url_for('scripts'))


@app.route('/scripts/<int:script_id>/delete', methods=['POST'])
def delete_script(script_id):
    script_model.delete(script_id)
    return redirect(url_for('scripts'))


# -------------------------------------------------------------------- people

@app.route('/people')
def people():
    everyone = person_model.all()
    return render_template('people.html', people=everyone)


@app.route('/people/new', methods=['GET', 'POST'])
@app.route('/people/<int:person_id>/edit', methods=['GET', 'POST'])
def person_form(person_id=None):
    existing = person_model.get(person_id) if person_id else None
    if request.method == 'POST':
        args = (
            request.form.get('name', '').strip(),
            request.form.get('relationship', '').strip(),
            request.form.get('stakes', 'medium'),
            request.form.get('patience', 'unknown'),
            request.form.get('holding_ok') == 'on',
            request.form.get('notes', '').strip(),
        )
        if existing:
            person_model.update(person_id, *args)
        else:
            person_model.create(*args)
        flash("Saved.", 'good')
        return redirect(url_for('people'))
    return render_template('person_form.html', person=existing)


# ------------------------------------------------------------------- amnesty

@app.route('/amnesty')
def amnesty():
    """The backlog cliff.

    Past a certain age a thread stops being a task and becomes a monument, and
    people abandon whole friendships rather than climb it. This gives the pile a
    single honest exit that takes one tap.
    """
    return render_template('amnesty.html', stale=thread_model.stale(days=5),
                           template=AMNESTY_TEXT)


AMNESTY_TEXT = ("Doing a clean-up of my messages and found this one buried. "
                "I'm sorry - it's not about you, my phone just gets away from me. "
                "Still glad you wrote. If it's still relevant I'd love to pick it up.")


@app.route('/amnesty/send', methods=['POST'])
def amnesty_send():
    body = request.form.get('body', AMNESTY_TEXT).strip()
    ids = request.form.getlist('thread_ids')
    for raw in ids:
        thread_model.add_message(int(raw), 'out', body, kind='amnesty')
        thread_model.set_state(int(raw), 'amnestied')
    if ids:
        flash(f"{len(ids)} cleared. The pile is not a monument any more.", 'good')
    return redirect(url_for('now'))


# --------------------------------------------------------------------- proof

@app.route('/proof')
def proof():
    """Evidence, not gamification. Counts what happened, never what you owe."""
    return render_template('proof.html', tally=outcome_model.tally(),
                           outcomes=outcome_model.all(),
                           windows=window_model.recent(),
                           ask=session.get('ask_outcome'),
                           ask_thread=thread_model.get(session['ask_outcome'])
                           if session.get('ask_outcome') else None)


@app.route('/about')
def about():
    return render_template('about.html')


if __name__ == '__main__':
    db.init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
