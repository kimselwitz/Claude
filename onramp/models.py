"""
Database models for Onramp.

Design note: the schema separates two things that texting anxiety tends to fuse
together - how much *you* feel is riding on a reply (people.stakes) and how the
other person *actually* reacts to a slow one (people.patience). Keeping them in
different columns is the whole point; the UI shows them side by side so the gap
is visible.
"""
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional


ISO = "%Y-%m-%d %H:%M:%S"


def now_str() -> str:
    return datetime.now().strftime(ISO)


def parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.strptime(ts, ISO)
    except ValueError:
        return None


class Database:
    """Database connection handler"""

    def __init__(self, db_path: Optional[str] = None):
        # ONRAMP_DB lets the tests point at a throwaway file.
        self.db_path = db_path or os.environ.get("ONRAMP_DB", "onramp.db")

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # People you text. `stakes` is felt pressure, `patience` is observed reality.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                relationship TEXT,
                stakes TEXT NOT NULL DEFAULT 'medium',
                patience TEXT NOT NULL DEFAULT 'unknown',
                holding_ok INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # A thread is one conversation sitting in one of a few states.
        # state: unopened | waiting | holding_sent | answered | no_reply_needed | amnestied
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                state TEXT NOT NULL DEFAULT 'unopened',
                reply_needed TEXT,
                effort TEXT,
                snoozed_until TIMESTAMP,
                last_inbound_at TIMESTAMP,
                last_outbound_at TIMESTAMP,
                opened_at TIMESTAMP,
                closed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (person_id) REFERENCES people (id)
            )
        ''')

        # direction: in | out.  kind: normal | holding | ack | amnesty
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                direction TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'normal',
                body TEXT NOT NULL,
                sent_at TIMESTAMP,
                FOREIGN KEY (thread_id) REFERENCES threads (id)
            )
        ''')

        # Reusable phrases. slot lets the assembler build a reply from parts.
        # slot: holding | opener | middle | closer | decline | standalone
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot TEXT NOT NULL,
                text TEXT NOT NULL,
                use_count INTEGER NOT NULL DEFAULT 0,
                is_builtin INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # A time-boxed batch of replying. Deliberately not a streak.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                planned_minutes INTEGER NOT NULL,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                threads_touched INTEGER NOT NULL DEFAULT 0
            )
        ''')

        # The evidence log: after a late reply, did the feared thing happen?
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                days_late INTEGER,
                went_badly INTEGER NOT NULL DEFAULT 0,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (thread_id) REFERENCES threads (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        conn.commit()
        conn.close()


class Person:
    def __init__(self, db: Database):
        self.db = db

    def all(self) -> List[Dict]:
        conn = self.db.get_connection()
        rows = conn.execute("SELECT * FROM people ORDER BY name").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get(self, person_id: int) -> Optional[Dict]:
        conn = self.db.get_connection()
        row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def create(self, name, relationship, stakes, patience, holding_ok, notes) -> int:
        conn = self.db.get_connection()
        cur = conn.execute(
            """INSERT INTO people (name, relationship, stakes, patience, holding_ok, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, relationship, stakes, patience, 1 if holding_ok else 0, notes),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return new_id

    def update(self, person_id, name, relationship, stakes, patience, holding_ok, notes):
        conn = self.db.get_connection()
        conn.execute(
            """UPDATE people SET name = ?, relationship = ?, stakes = ?, patience = ?,
                                 holding_ok = ?, notes = ? WHERE id = ?""",
            (name, relationship, stakes, patience, 1 if holding_ok else 0, notes, person_id),
        )
        conn.commit()
        conn.close()


class Thread:
    """Threads plus the derived fields the UI leans on (age, temperature)."""

    OPEN_STATES = ("unopened", "waiting", "holding_sent")

    def __init__(self, db: Database):
        self.db = db

    def _decorate(self, row: sqlite3.Row) -> Dict:
        t = dict(row)
        last_in = parse(t.get("last_inbound_at"))
        t["age_hours"] = (datetime.now() - last_in).total_seconds() / 3600 if last_in else 0
        t["age_words"] = age_words(last_in)
        t["temperature"] = temperature(t["age_hours"])
        snooze = parse(t.get("snoozed_until"))
        t["is_snoozed"] = bool(snooze and snooze > datetime.now())
        t["snooze_words"] = age_words(snooze, future=True) if snooze else None
        return t

    def _query(self, where: str, params: tuple = ()) -> List[Dict]:
        conn = self.db.get_connection()
        rows = conn.execute(
            f"""SELECT t.*, p.name AS person_name, p.stakes, p.patience,
                       p.holding_ok, p.notes AS person_notes, p.relationship,
                       (SELECT body FROM messages m WHERE m.thread_id = t.id
                        AND m.direction = 'in' ORDER BY m.sent_at DESC LIMIT 1) AS last_message
                FROM threads t JOIN people p ON p.id = t.person_id
                WHERE {where}""",
            params,
        ).fetchall()
        conn.close()
        return [self._decorate(r) for r in rows]

    def get(self, thread_id: int) -> Optional[Dict]:
        found = self._query("t.id = ?", (thread_id,))
        return found[0] if found else None

    def unopened(self) -> List[Dict]:
        rows = self._query("t.state = 'unopened'")
        return sorted(rows, key=lambda t: -t["age_hours"])

    def open_threads(self, include_snoozed: bool = False) -> List[Dict]:
        """Everything still owed a reply, cheapest-first.

        Sorting by effort rather than by urgency is deliberate. Urgency-first
        ordering puts the hardest message on top, which is where the avoidance
        starts. Cheap wins first builds enough momentum to reach the hard one.
        """
        rows = self._query("t.state IN ('waiting', 'holding_sent')")
        if not include_snoozed:
            rows = [t for t in rows if not t["is_snoozed"]]
        effort_rank = {"tiny": 0, "small": 1, "real": 2, None: 1}
        return sorted(rows, key=lambda t: (effort_rank.get(t["effort"], 1), -t["age_hours"]))

    def stale(self, days: int = 5) -> List[Dict]:
        rows = self._query("t.state IN ('waiting', 'holding_sent')")
        return sorted([t for t in rows if t["age_hours"] >= days * 24],
                      key=lambda t: -t["age_hours"])

    def messages(self, thread_id: int) -> List[Dict]:
        conn = self.db.get_connection()
        rows = conn.execute(
            "SELECT * FROM messages WHERE thread_id = ? ORDER BY sent_at, id", (thread_id,)
        ).fetchall()
        conn.close()
        out = []
        for r in rows:
            m = dict(r)
            m["when_words"] = age_words(parse(m["sent_at"]))
            out.append(m)
        return out

    def mark_opened(self, thread_id: int):
        conn = self.db.get_connection()
        conn.execute(
            """UPDATE threads SET opened_at = COALESCE(opened_at, ?),
               state = CASE WHEN state = 'unopened' THEN 'waiting' ELSE state END
               WHERE id = ?""",
            (now_str(), thread_id),
        )
        conn.commit()
        conn.close()

    def triage(self, thread_id: int, reply_needed: str, effort: str):
        state = "waiting" if reply_needed in ("yes", "ack") else "no_reply_needed"
        closed = None if state == "waiting" else now_str()
        conn = self.db.get_connection()
        conn.execute(
            """UPDATE threads SET reply_needed = ?, effort = ?, state = ?,
                                  opened_at = COALESCE(opened_at, ?), closed_at = ?
               WHERE id = ?""",
            (reply_needed, effort, state, now_str(), closed, thread_id),
        )
        conn.commit()
        conn.close()

    def set_state(self, thread_id: int, state: str):
        closed = now_str() if state in ("answered", "no_reply_needed", "amnestied") else None
        conn = self.db.get_connection()
        conn.execute("UPDATE threads SET state = ?, closed_at = ? WHERE id = ?",
                     (state, closed, thread_id))
        conn.commit()
        conn.close()

    def snooze(self, thread_id: int, hours: int):
        until = (datetime.now() + timedelta(hours=hours)).strftime(ISO)
        conn = self.db.get_connection()
        conn.execute("UPDATE threads SET snoozed_until = ? WHERE id = ?", (until, thread_id))
        conn.commit()
        conn.close()

    def unsnooze(self, thread_id: int):
        conn = self.db.get_connection()
        conn.execute("UPDATE threads SET snoozed_until = NULL WHERE id = ?", (thread_id,))
        conn.commit()
        conn.close()

    def add_message(self, thread_id: int, direction: str, body: str, kind: str = "normal",
                    sent_at: Optional[str] = None):
        stamp = sent_at or now_str()
        conn = self.db.get_connection()
        conn.execute(
            "INSERT INTO messages (thread_id, direction, kind, body, sent_at) VALUES (?, ?, ?, ?, ?)",
            (thread_id, direction, kind, body, stamp),
        )
        column = "last_inbound_at" if direction == "in" else "last_outbound_at"
        conn.execute(f"UPDATE threads SET {column} = ? WHERE id = ?", (stamp, thread_id))
        conn.commit()
        conn.close()

    def create(self, person_id: int, state: str = "unopened") -> int:
        conn = self.db.get_connection()
        cur = conn.execute("INSERT INTO threads (person_id, state) VALUES (?, ?)",
                           (person_id, state))
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return new_id


class Script:
    def __init__(self, db: Database):
        self.db = db

    def by_slot(self, slot: str) -> List[Dict]:
        conn = self.db.get_connection()
        rows = conn.execute(
            "SELECT * FROM scripts WHERE slot = ? ORDER BY use_count DESC, id", (slot,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def all_grouped(self) -> Dict[str, List[Dict]]:
        conn = self.db.get_connection()
        rows = conn.execute("SELECT * FROM scripts ORDER BY use_count DESC, id").fetchall()
        conn.close()
        grouped: Dict[str, List[Dict]] = {}
        for r in rows:
            grouped.setdefault(r["slot"], []).append(dict(r))
        return grouped

    def add(self, slot: str, text: str) -> int:
        conn = self.db.get_connection()
        cur = conn.execute("INSERT INTO scripts (slot, text) VALUES (?, ?)", (slot, text))
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return new_id

    def delete(self, script_id: int):
        conn = self.db.get_connection()
        conn.execute("DELETE FROM scripts WHERE id = ?", (script_id,))
        conn.commit()
        conn.close()

    def used(self, text: str):
        conn = self.db.get_connection()
        conn.execute("UPDATE scripts SET use_count = use_count + 1 WHERE text = ?", (text,))
        conn.commit()
        conn.close()


class Window:
    def __init__(self, db: Database):
        self.db = db

    def active(self) -> Optional[Dict]:
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT * FROM windows WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if not row:
            return None
        w = dict(row)
        started = parse(w["started_at"])
        elapsed = (datetime.now() - started).total_seconds() / 60 if started else 0
        w["minutes_left"] = max(0, round(w["planned_minutes"] - elapsed))
        w["expired"] = elapsed >= w["planned_minutes"]
        return w

    def start(self, minutes: int) -> int:
        self.end_all()
        conn = self.db.get_connection()
        cur = conn.execute(
            "INSERT INTO windows (planned_minutes, started_at) VALUES (?, ?)",
            (minutes, now_str()),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return new_id

    def end_all(self):
        conn = self.db.get_connection()
        conn.execute("UPDATE windows SET ended_at = ? WHERE ended_at IS NULL", (now_str(),))
        conn.commit()
        conn.close()

    def touch(self):
        conn = self.db.get_connection()
        conn.execute(
            """UPDATE windows SET threads_touched = threads_touched + 1
               WHERE ended_at IS NULL"""
        )
        conn.commit()
        conn.close()

    def recent(self, limit: int = 10) -> List[Dict]:
        conn = self.db.get_connection()
        rows = conn.execute(
            "SELECT * FROM windows WHERE ended_at IS NOT NULL ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


class Outcome:
    def __init__(self, db: Database):
        self.db = db

    def log(self, thread_id: int, days_late: int, went_badly: bool, note: str = ""):
        conn = self.db.get_connection()
        conn.execute(
            "INSERT INTO outcomes (thread_id, days_late, went_badly, note) VALUES (?, ?, ?, ?)",
            (thread_id, days_late, 1 if went_badly else 0, note),
        )
        conn.commit()
        conn.close()

    def all(self) -> List[Dict]:
        conn = self.db.get_connection()
        rows = conn.execute(
            """SELECT o.*, p.name AS person_name FROM outcomes o
               JOIN threads t ON t.id = o.thread_id
               JOIN people p ON p.id = t.person_id
               ORDER BY o.id DESC"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def tally(self) -> Dict:
        rows = self.all()
        return {
            "total": len(rows),
            "badly": sum(1 for r in rows if r["went_badly"]),
            "fine": sum(1 for r in rows if not r["went_badly"]),
            "worst_late": max([r["days_late"] or 0 for r in rows], default=0),
        }


def temperature(age_hours: float) -> str:
    """Never 'overdue'. Four bands, none of which are an emergency."""
    if age_hours < 6:
        return "easy"      # the cheap window - a one-liner now costs nothing
    if age_hours < 36:
        return "warm"
    if age_hours < 24 * 5:
        return "cooling"
    return "cold"


TEMPERATURE_WORDS = {
    "easy": "still easy",
    "warm": "still warm",
    "cooling": "cooling off",
    "cold": "gone cold",
}


def age_words(dt: Optional[datetime], future: bool = False) -> str:
    """Plain language, not '4d'. Precise counters make time blindness worse,
    not better - they turn into a score."""
    if not dt:
        return "whenever"
    now = datetime.now()
    delta = (dt - now) if future else (now - dt)
    hours = delta.total_seconds() / 3600
    if hours < 0:
        return "now"
    if hours < 1:
        return "in a few minutes" if future else "just now"
    if hours < 6:
        return f"in {int(hours)} hours" if future else "earlier today"
    if hours < 24 and dt.date() == now.date():
        return "later today" if future else "this morning"
    days = abs((now.date() - dt.date()).days)
    if days == 1:
        return "tomorrow" if future else "yesterday"
    if days < 7:
        return f"on {dt.strftime('%A')}" if future else f"since {dt.strftime('%A')}"
    if days < 11:
        return "next week" if future else "since last week"
    if days < 25:
        return "in a couple of weeks" if future else "a couple of weeks ago"
    if days < 60:
        return f"in {dt.strftime('%B')}" if future else f"about a month ago"
    return f"back in {dt.strftime('%B')}" 
