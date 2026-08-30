# -*- coding: utf-8 -*-
"""Tests for the rules that decide who gets texted, when, and in what language."""
import os
import sys
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
import db
import messaging
import models
import nudges
import seed


class FailingProvider:
    name = "failing"

    def send(self, to, body, sms_from=None):
        return messaging.SendResult(False, error="carrier rejected")


class RecordingProvider:
    name = "recording"

    def __init__(self):
        self.sent = []

    def send(self, to, body, sms_from=None):
        self.sent.append((to, body))
        return messaging.SendResult(True, provider_ref="ref-%d" % len(self.sent))


class Base(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        db.init_db(self.conn)
        self.org_id = seed.seed_org(self.conn, "Test Agency")
        self.user_id = models.create_user(self.conn, self.org_id, "tester", "pw", "Tester", "admin")
        self.org = models.get_org(self.conn, self.org_id)
        self.types = {row["name"]: row["id"]
                      for row in models.list_document_types(self.conn, self.org_id)}

    def tearDown(self):
        self.conn.close()

    def make_contact(self, first="Ana", last="Reyes", phone="207-555-0142",
                     language="es", consent=1):
        return models.create_contact(self.conn, self.org_id, {
            "first_name": first, "last_name": last, "phone": phone,
            "preferred_language": language, "consent_sms": consent})

    def contact(self, contact_id):
        return models.get_contact(self.conn, self.org_id, contact_id)


class PhoneTests(unittest.TestCase):
    def test_normalizes_common_formats(self):
        for raw in ["2075550142", "207-555-0142", "(207) 555-0142", "+1 207 555 0142",
                    "1-207-555-0142"]:
            self.assertEqual(messaging.normalize_phone(raw), "+12075550142", raw)

    def test_blank_and_display(self):
        self.assertIsNone(messaging.normalize_phone(""))
        self.assertEqual(messaging.format_phone("+12075550142"), "(207) 555-0142")


class RenderTests(unittest.TestCase):
    def test_substitutes_and_lists_fields(self):
        body = "Hi {{first_name}}, we need {{document_name}} by {{due_date}}."
        self.assertEqual(
            messaging.render(body, {"first_name": "Ana", "document_name": "ID",
                                    "due_date": "Sep 3"}),
            "Hi Ana, we need ID by Sep 3.")
        self.assertEqual(messaging.merge_fields(body),
                         ["document_name", "due_date", "first_name"])

    def test_missing_field_becomes_empty_not_crash(self):
        self.assertEqual(messaging.render("Hi {{nobody}}!", {}), "Hi !")


class SegmentTests(unittest.TestCase):
    def test_plain_english_is_gsm7(self):
        info = messaging.segment_info("Your pay stub is due Friday.")
        self.assertEqual(info["encoding"], "GSM-7")
        self.assertEqual(info["segments"], 1)

    def test_accents_force_ucs2_and_shrink_the_segment(self):
        info = messaging.segment_info("Comprobante de ingresos: atención requerida.")
        self.assertEqual(info["encoding"], "UCS-2")
        self.assertEqual(info["per_segment"], 70)
        self.assertIn("ó", messaging.non_gsm_characters("atención"))

    def test_long_message_splits(self):
        self.assertEqual(messaging.segment_info("a" * 200)["segments"], 2)


class QuietHoursTests(unittest.TestCase):
    def test_overnight_window_wraps_midnight(self):
        self.assertTrue(messaging.in_quiet_hours(datetime(2026, 9, 1, 22, 0), 21, 8))
        self.assertTrue(messaging.in_quiet_hours(datetime(2026, 9, 1, 3, 0), 21, 8))
        self.assertFalse(messaging.in_quiet_hours(datetime(2026, 9, 1, 12, 0), 21, 8))
        self.assertFalse(messaging.in_quiet_hours(datetime(2026, 9, 1, 8, 0), 21, 8))

    def test_next_send_time(self):
        self.assertEqual(messaging.next_send_time(datetime(2026, 9, 1, 22, 30), 21, 8),
                         datetime(2026, 9, 2, 8, 0))
        self.assertEqual(messaging.next_send_time(datetime(2026, 9, 1, 6, 30), 21, 8),
                         datetime(2026, 9, 1, 8, 0))
        noon = datetime(2026, 9, 1, 12, 0)
        self.assertEqual(messaging.next_send_time(noon, 21, 8), noon)


class ConsentTests(Base):
    def test_reachability_reasons(self):
        no_phone = self.contact(self.make_contact(phone=None, consent=1))
        self.assertEqual(messaging.reachability(no_phone)[1], "No mobile number on file")

        no_consent = self.contact(self.make_contact(consent=0))
        self.assertEqual(messaging.reachability(no_consent)[1], "No SMS consent recorded")

        opted_out_id = self.make_contact()
        models.set_opt_out(self.conn, self.org_id, opted_out_id, True)
        self.assertEqual(messaging.reachability(self.contact(opted_out_id))[1],
                         "Opted out of text messages")

        ok, _reason = messaging.reachability(self.contact(self.make_contact()))
        self.assertTrue(ok)

    def test_queue_refuses_unreachable_contact(self):
        contact = self.contact(self.make_contact(consent=0))
        with self.assertRaises(messaging.Blocked):
            messaging.queue_message(self.conn, self.org, contact, "hello")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 0)

    def test_opt_out_cancels_queued_messages(self):
        contact_id = self.make_contact()
        contact = self.contact(contact_id)
        messaging.queue_message(self.conn, self.org, contact, "hello",
                                now=datetime(2026, 9, 1, 23, 0))  # held overnight
        models.set_opt_out(self.conn, self.org_id, contact_id, True)
        statuses = [row["status"] for row in
                    self.conn.execute("SELECT status FROM messages WHERE direction = 'out'")]
        self.assertEqual(statuses, ["canceled"])


class DispatchTests(Base):
    def test_quiet_hours_hold_then_send(self):
        contact = self.contact(self.make_contact())
        late = datetime(2026, 9, 1, 23, 30)
        message_id = messaging.queue_message(self.conn, self.org, contact, "hola", now=late)
        row = self.conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        self.assertEqual(row["status"], "held")
        self.assertEqual(row["scheduled_for"], "2026-09-02 08:00:00")

        provider = RecordingProvider()
        sent, failed = messaging.dispatch_due(self.conn, self.org_id, provider, now=late)
        self.assertEqual((sent, failed), (0, 0), "nothing may go out overnight")

        sent, failed = messaging.dispatch_due(self.conn, self.org_id, provider,
                                              now=datetime(2026, 9, 2, 8, 5))
        self.assertEqual((sent, failed), (1, 0))
        self.assertEqual(provider.sent[0][0], "+12075550142")

    def test_provider_failure_is_recorded_not_swallowed(self):
        contact = self.contact(self.make_contact())
        messaging.queue_message(self.conn, self.org, contact, "hola",
                                now=datetime(2026, 9, 1, 10, 0))
        sent, failed = messaging.dispatch_due(self.conn, self.org_id, FailingProvider(),
                                              now=datetime(2026, 9, 1, 10, 0))
        self.assertEqual((sent, failed), (0, 1))
        row = self.conn.execute("SELECT status, error FROM messages").fetchone()
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["error"], "carrier rejected")

    def test_dispatch_is_idempotent(self):
        contact = self.contact(self.make_contact())
        messaging.queue_message(self.conn, self.org, contact, "hola",
                                now=datetime(2026, 9, 1, 10, 0))
        provider = RecordingProvider()
        messaging.dispatch_due(self.conn, self.org_id, provider, now=datetime(2026, 9, 1, 10, 0))
        messaging.dispatch_due(self.conn, self.org_id, provider, now=datetime(2026, 9, 1, 10, 1))
        self.assertEqual(len(provider.sent), 1)


class InboundTests(Base):
    def test_stop_opts_out_in_any_supported_language(self):
        for index, keyword in enumerate(["STOP", "alto", "Joogso", "arret", "PARE"]):
            contact_id = self.make_contact(phone="207-555-0%03d" % (200 + index))
            messaging.receive_inbound(self.conn, self.contact(contact_id)["phone"], keyword)
            self.assertEqual(self.contact(contact_id)["opted_out"], 1, keyword)

    def test_stop_covers_everyone_sharing_that_phone(self):
        """Households share a number. A STOP from it must silence all of them."""
        shared = "207-555-0311"
        parent = self.make_contact(first="Rosa", phone=shared)
        child = self.make_contact(first="Luis", phone=shared)
        messaging.receive_inbound(self.conn, shared, "STOP")
        self.assertEqual(self.contact(parent)["opted_out"], 1)
        self.assertEqual(self.contact(child)["opted_out"], 1)

    def test_start_resubscribes_and_records_consent(self):
        contact_id = self.make_contact(consent=0)
        phone = self.contact(contact_id)["phone"]
        messaging.receive_inbound(self.conn, phone, "START")
        contact = self.contact(contact_id)
        self.assertEqual(contact["opted_out"], 0)
        self.assertEqual(contact["consent_sms"], 1)
        self.assertIsNotNone(contact["consent_at"])

    def test_ordinary_reply_is_stored_as_a_reply(self):
        contact_id = self.make_contact()
        message_id, intent, _contact = messaging.receive_inbound(
            self.conn, self.contact(contact_id)["phone"], "sending the photo tonight")
        self.assertEqual(intent, "reply")
        row = self.conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        self.assertEqual(row["direction"], "in")
        self.assertEqual(row["status"], "received")

    def test_unknown_number_is_not_stored(self):
        message_id, intent, contact = messaging.receive_inbound(self.conn, "+12075559999", "hi")
        self.assertIsNone(message_id)
        self.assertEqual(intent, "unknown")
        self.assertIsNone(contact)


class TemplateTests(Base):
    def test_participant_language_is_used(self):
        language, body = messaging.pick_variant(self.conn, "doc_overdue", self.org_id, "so")
        self.assertEqual(language, "so")
        self.assertIn("Salaan", body)

    def test_falls_back_to_english_when_untranslated(self):
        template_id = models.create_template(self.conn, self.org_id, "custom", "Custom")
        models.save_variants(self.conn, template_id, {"en": "English only"})
        language, body = messaging.pick_variant(self.conn, "custom", self.org_id, "ar")
        self.assertEqual((language, body), ("en", "English only"))

    def test_blank_variant_is_removed(self):
        template_id = models.create_template(self.conn, self.org_id, "custom2", "Custom 2")
        models.save_variants(self.conn, template_id, {"en": "hi", "es": "hola"})
        models.save_variants(self.conn, template_id, {"es": "  "})
        self.assertEqual(set(models.template_variants(self.conn, template_id)), {"en"})


class NudgeTests(Base):
    def setUp(self):
        super().setUp()
        self.contact_id = self.make_contact()
        self.today = date.today()

    def request_due_in(self, days, document="Proof of income", contact_id=None):
        return models.create_request(
            self.conn, self.org_id, contact_id or self.contact_id, self.types[document],
            (self.today + timedelta(days=days)).isoformat())

    def test_rule_matches_its_offset_and_fires_once(self):
        self.request_due_in(3)
        first = nudges.run(self.conn, self.org_id)
        self.assertEqual([row["status"] for row in first], ["queued"])
        second = nudges.run(self.conn, self.org_id)
        self.assertEqual(second, [], "a rule must never nudge the same request twice")

    def test_message_is_in_the_participants_language_including_document_name(self):
        self.request_due_in(3)
        results = nudges.run(self.conn, self.org_id)
        body = self.conn.execute("SELECT body FROM messages").fetchone()["body"]
        self.assertEqual(results[0]["language"], "es")
        self.assertIn("Hola Ana", body)
        self.assertIn("Comprobante de ingresos", body)
        self.assertNotIn("Proof of income", body)

    def test_unreachable_participant_is_skipped_with_a_reason(self):
        quiet = self.make_contact(first="Samir", phone="207-555-0187", language="ar", consent=0)
        self.request_due_in(3, contact_id=quiet)
        results = nudges.run(self.conn, self.org_id)
        self.assertEqual([row["status"] for row in results], ["skipped"])
        self.assertEqual(results[0]["reason"], "No SMS consent recorded")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 0)

    def test_only_the_matching_offset_fires(self):
        self.request_due_in(5)            # no rule at 5 days out
        self.assertEqual(nudges.run(self.conn, self.org_id), [])

    def test_dry_run_queues_nothing(self):
        self.request_due_in(0)
        results = nudges.run(self.conn, self.org_id, dry_run=True)
        self.assertEqual(results[0]["status"], "queued")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM nudge_log").fetchone()[0], 0)

    def test_closed_request_stops_being_nudged(self):
        request_id = self.request_due_in(3)
        models.set_request_status(self.conn, self.org_id, request_id, "received")
        self.assertEqual(nudges.run(self.conn, self.org_id), [])


class MetricsTests(Base):
    def test_counts_and_turnaround(self):
        contact_id = self.make_contact()
        today = date.today()
        models.create_request(self.conn, self.org_id, contact_id, self.types["Photo ID"],
                              (today - timedelta(days=4)).isoformat())
        models.create_request(self.conn, self.org_id, contact_id, self.types["Bank statement"],
                              (today + timedelta(days=2)).isoformat())
        done = models.create_request(self.conn, self.org_id, contact_id,
                                     self.types["Proof of income"], today.isoformat())
        self.conn.execute("UPDATE document_requests SET requested_at = ? WHERE id = ?",
                          ((today - timedelta(days=6)).isoformat() + " 09:00:00", done))
        models.set_request_status(self.conn, self.org_id, done, "verified")

        metrics = models.dashboard_metrics(self.conn, self.org_id)
        self.assertEqual(metrics["open_requests"], 2)
        self.assertEqual(metrics["overdue_requests"], 1)
        self.assertEqual(metrics["due_soon"], 1)
        self.assertEqual(metrics["completed_90d"], 1)
        self.assertAlmostEqual(metrics["median_days_to_receipt"], 6, delta=1)
        self.assertEqual(metrics["reachable"], 1)
        self.assertEqual(metrics["reachable_pct"], 100.0)


class WebTests(Base):
    """Every page a caseworker can reach must render."""

    def setUp(self):
        super().setUp()
        self.db_path = "/tmp/doorway_web_test.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        conn = db.connect(self.db_path)
        db.init_db(conn)
        self.web_org = seed.seed_org(conn, "Web Test Agency")
        models.create_user(conn, self.web_org, "webtester", "pw", "Web Tester", "admin")
        self.contact_ids = seed.seed_demo(conn, self.web_org)
        conn.close()

        self.flask_app = app_module.create_app(self.db_path, secret_key="test")
        self.flask_app.config["TESTING"] = True
        self.client = self.flask_app.test_client()
        self.client.post("/login", data={"username": "webtester", "password": "pw"})

    def tearDown(self):
        super().tearDown()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_login_is_required(self):
        anonymous = self.flask_app.test_client()
        response = anonymous.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_every_page_renders(self):
        paths = ["/", "/participants", "/participants/new", "/participants/1",
                 "/requests", "/requests?scope=overdue", "/requests/new", "/templates",
                 "/templates/1", "/templates/new", "/document-types",
                 "/document-types/1/names", "/reminders", "/messages", "/settings"]
        for path in paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, "%s returned %d"
                             % (path, response.status_code))

    def test_creating_a_request_texts_the_participant(self):
        response = self.client.post("/requests/new", data={
            "contact_id": self.contact_ids[0], "due_date": date.today().isoformat(),
            "document_type_id": ["1"], "send_now": "1"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        conn = db.connect(self.db_path)
        row = conn.execute("SELECT * FROM messages WHERE contact_id = ? ORDER BY id DESC",
                           (self.contact_ids[0],)).fetchone()
        conn.close()
        self.assertEqual(row["template_code"], "doc_request_new")
        self.assertEqual(row["language"], "es")

    def test_marking_received_closes_the_request(self):
        conn = db.connect(self.db_path)
        request_id = conn.execute(
            "SELECT id FROM document_requests WHERE status = 'open' LIMIT 1").fetchone()["id"]
        conn.close()
        self.client.post("/requests/%d/status" % request_id,
                         data={"status": "received", "thank_them": "1"}, follow_redirects=True)
        conn = db.connect(self.db_path)
        row = conn.execute("SELECT * FROM document_requests WHERE id = ?",
                           (request_id,)).fetchone()
        conn.close()
        self.assertEqual(row["status"], "received")
        self.assertIsNotNone(row["closed_at"])

    def test_inbound_webhook_records_stop(self):
        conn = db.connect(self.db_path)
        phone = conn.execute("SELECT phone FROM contacts WHERE id = ?",
                             (self.contact_ids[1],)).fetchone()["phone"]
        conn.close()
        anonymous = self.flask_app.test_client()
        response = anonymous.post("/sms/inbound", data={"From": phone, "Body": "STOP"})
        self.assertEqual(response.status_code, 200)
        conn = db.connect(self.db_path)
        row = conn.execute("SELECT opted_out FROM contacts WHERE id = ?",
                           (self.contact_ids[1],)).fetchone()
        conn.close()
        self.assertEqual(row["opted_out"], 1)

    def test_unknown_inbound_number_is_rejected(self):
        anonymous = self.flask_app.test_client()
        self.assertEqual(
            anonymous.post("/sms/inbound", data={"From": "+15085550000", "Body": "hi"}).status_code,
            404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
