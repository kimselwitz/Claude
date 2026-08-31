"""
End-to-end tests. Run with:  python test_onramp.py

Covers every route and every state transition, plus the two design rules that
are easy to break by accident later: no digits in the nav chrome, and the word
"overdue" appearing nowhere.
"""
import os
import sys
import tempfile

DB = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["ONRAMP_DB"] = DB
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import seed
from app import app, thread_model, db

seed.run()
app.config["TESTING"] = True
client = app.test_client()

passed, failed = 0, []


def ok(label, condition, detail=""):
    global passed
    if condition:
        passed += 1
        print(f"  ok    {label}")
    else:
        failed.append(label)
        print(f"  FAIL  {label} {detail}")


def get(label, url, contains=None):
    r = client.get(url)
    good = r.status_code == 200
    if good and contains:
        good = contains in r.get_data(as_text=True)
    ok(label, good, f"-> {r.status_code}")
    return r


def post(label, url, data=None):
    r = client.post(url, data=data or {})
    ok(label, r.status_code in (200, 302), f"-> {r.status_code}")
    return r


def state_of(tid):
    return thread_model.get(tid)["state"]


print("\nGET every screen")
get("now", "/", "Owed a reply")
get("triage", "/triage", "Does this actually need a reply")
get("scripts", "/scripts", "Holding replies")
get("people", "/people", "feels")
get("new person", "/people/new")
get("edit person", "/people/1/edit", "Maya")
get("amnesty", "/amnesty", "Amnesty")
get("proof", "/proof", "What actually happened")
get("about", "/about", "Why it works this way")

open_ids = [t["id"] for t in thread_model.open_threads()]
unopened_ids = [t["id"] for t in thread_model.unopened()]
get("thread", f"/thread/{open_ids[0]}", "Write the actual reply")

print("\nThe deck sorts cheapest-first, not most-urgent-first")
efforts = [t["effort"] for t in thread_model.open_threads()]
rank = {"tiny": 0, "small": 1, "real": 2}
ok("tiny before small before real", efforts == sorted(efforts, key=lambda e: rank[e]), efforts)

print("\nReply window")
post("start", "/window/start", {"minutes": 10})
get("now shows the timer", "/", "min left")

print("\nTriage: reading does not commit you")
post("close without replying", f"/triage/{unopened_ids[0]}",
     {"reply_needed": "no", "effort": "tiny"})
ok("state -> no_reply_needed", state_of(unopened_ids[0]) == "no_reply_needed")
post("needs a real reply", f"/triage/{unopened_ids[1]}",
     {"reply_needed": "yes", "effort": "real"})
ok("state -> waiting", state_of(unopened_ids[1]) == "waiting")

print("\nHolding reply counts as handling the thread")
t = open_ids[0]
post("send holding", f"/thread/{t}/holding", {"body": "Saw this — coming back tonight."})
ok("state -> holding_sent", state_of(t) == "holding_sent")

print("\nScript use_count rises with use")
post("send a known script", f"/thread/{open_ids[2]}/holding",
     {"body": "Got it! Give me a day, I want to answer this properly."})
conn = db.get_connection()
count = conn.execute("SELECT use_count FROM scripts WHERE text LIKE 'Got it!%'").fetchone()[0]
conn.close()
ok("use_count incremented", count == 1, f"got {count}")

print("\nSnooze removes it from the deck without closing it")
t2 = open_ids[1]
post("snooze 6h", f"/thread/{t2}/snooze", {"hours": 6})
ok("marked snoozed", thread_model.get(t2)["is_snoozed"])
ok("off the deck", t2 not in [x["id"] for x in thread_model.open_threads()])
get("listed under 'put off'", "/", "Put off for now")
post("reopen", f"/thread/{t2}/reopen")
ok("back on the deck", not thread_model.get(t2)["is_snoozed"])

print("\nA late reply asks once how it went")
late = [x for x in thread_model.open_threads() if x["age_hours"] >= 48][0]["id"]
post("send reply", f"/thread/{late}/reply",
     {"body": "Late reply, no drama. Yes I'm in!", "used_script": ["Hey!"]})
ok("state -> answered", state_of(late) == "answered")
get("proof asks", "/proof", "Did it go badly")
post("log outcome", f"/thread/{late}/outcome", {"went_badly": "no", "note": "totally normal"})
get("tally shows it", "/proof", "went fine")

print("\nScripts CRUD")
post("add", "/scripts/add", {"text": "Can we do voice notes instead?", "slot": "middle"})
get("listed", "/scripts", "voice notes")
conn = db.get_connection()
sid = conn.execute("SELECT id FROM scripts WHERE text LIKE '%voice notes%'").fetchone()[0]
conn.close()
post("delete", f"/scripts/{sid}/delete")

print("\nPeople CRUD")
post("create", "/people/new", {"name": "Nadia", "relationship": "cousin", "stakes": "low",
                               "patience": "fine", "holding_ok": "on", "notes": "voice notes"})
get("listed", "/people", "Nadia")
conn = db.get_connection()
pid = conn.execute("SELECT id FROM people WHERE name='Nadia'").fetchone()[0]
conn.close()
post("edit", f"/people/{pid}/edit", {"name": "Nadia", "relationship": "cousin",
                                     "stakes": "low", "patience": "hurt", "notes": ""})

print("\nAmnesty clears the cold pile in one go")
stale = thread_model.stale(days=5)
ok("there is a cold pile to clear", len(stale) > 0, f"{len(stale)} threads")
post("send amnesty", "/amnesty/send",
     {"body": "Doing a clean-up and found this buried.",
      "thread_ids": [str(s["id"]) for s in stale]})
ok("all amnestied", all(state_of(s["id"]) == "amnestied" for s in stale))

print("\nWindow closes; empty deck still renders")
post("end window", "/window/end")
get("empty-ish deck", "/")

print("\nBad input is refused quietly, never with an error page")
r = client.get("/thread/99999")
ok("missing thread redirects home", r.status_code == 302, f"-> {r.status_code}")
r = client.post(f"/thread/{open_ids[0]}/reply", data={"body": "   "})
ok("whitespace reply not sent", r.status_code == 302)
post("empty holding refused", f"/thread/{open_ids[0]}/holding", {"body": ""})
post("blank script ignored", "/scripts/add", {"text": "  ", "slot": "middle"})

print("\nDesign rules that must not regress")
html = client.get("/").get_data(as_text=True)
nav = html[html.index('<nav class="tabs">'):].split("</nav>")[0]
ok("no count badge: nav contains no digits", not any(c.isdigit() for c in nav))
ok("the word 'overdue' appears nowhere", "overdue" not in html.lower())
# "streak" on its own would false-positive on the Proof page, which exists partly
# to say it is not one. Match the gamified phrasings instead.
ALARM = ["urgent", "you're behind", "overdue", "keep your streak", "streak of",
         "day streak", "don't break"]
for screen in ["/", "/triage", "/amnesty", "/proof", "/scripts", "/people"]:
    body = client.get(screen).get_data(as_text=True).lower()
    hits = [w for w in ALARM if w in body]
    ok(f"no alarm language on {screen}", not hits, hits)

ok("proof page disavows streaks outright",
   "not a streak" in client.get("/proof").get_data(as_text=True).lower())

print(f"\n{passed} passed, {len(failed)} failed")
if failed:
    print("failures:", failed)
sys.exit(1 if failed else 0)
