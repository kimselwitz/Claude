# -*- coding: utf-8 -*-
"""
Doorway -- participant communication and document chasing for housing programs.

Web layer only: every rule about who may be texted, when, and in what language
lives in messaging.py and nudges.py so it can be tested without a browser.
"""
import hmac
import os
from datetime import date, datetime
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)

import db
import languages
import messaging
import models
import nudges
import seed


def is_production():
    return os.environ.get("DOORWAY_ENV", "").lower() == "production"


def resolve_secret_key(explicit=None):
    """Session-signing key.

    In production this must come from the environment. A deployed Doorway holds
    names, phone numbers, and message history, so quietly falling back to a
    known development key would let anyone forge a staff session.
    """
    key = explicit or os.environ.get("DOORWAY_SECRET_KEY")
    if key:
        return key
    if is_production():
        raise RuntimeError(
            "DOORWAY_SECRET_KEY must be set when DOORWAY_ENV=production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"")
    return "dev-secret-change-me"


def create_app(db_path=None, secret_key=None):
    app = Flask(__name__)
    app.config["DATABASE"] = db_path or db.DEFAULT_DB_PATH
    app.config["SECRET_KEY"] = resolve_secret_key(secret_key)
    # Staff sessions carry access to participant PII: keep the cookie away from
    # JavaScript and off cross-site requests, and require HTTPS once deployed.
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=is_production(),
    )

    # ------------------------------------------------------------------
    # Request plumbing
    # ------------------------------------------------------------------

    def get_conn():
        if "conn" not in g:
            g.conn = db.connect(app.config["DATABASE"])
        return g.conn

    @app.teardown_appcontext
    def close_conn(_exception):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    @app.before_request
    def load_user():
        g.user = None
        g.org = None
        user_id = session.get("user_id")
        if user_id:
            g.user = models.get_user(get_conn(), user_id)
            if g.user:
                g.org = models.get_org(get_conn(), g.user["org_id"])

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            if g.user["role"] != "admin":
                abort(403)
            return view(*args, **kwargs)
        return wrapped

    # ------------------------------------------------------------------
    # Template helpers
    # ------------------------------------------------------------------

    @app.template_filter("phone")
    def phone_filter(value):
        return messaging.format_phone(value)

    @app.template_filter("lang")
    def lang_filter(code):
        return languages.label_for(code)

    @app.template_filter("shortdate")
    def shortdate_filter(value):
        if not value:
            return ""
        text = str(value)
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:len(fmt) + 2].strip(), fmt).strftime("%b %-d, %Y")
            except ValueError:
                continue
        return text

    @app.template_filter("datetime")
    def datetime_filter(value):
        if not value:
            return ""
        try:
            return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").strftime(
                "%b %-d, %-I:%M %p")
        except ValueError:
            return str(value)

    @app.context_processor
    def inject_globals():
        pending = 0
        overdue = 0
        if g.get("org"):
            conn = get_conn()
            pending = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE org_id = ? AND direction = 'out'"
                " AND status IN ('queued', 'held')", (g.org["id"],)).fetchone()[0]
            overdue = conn.execute(
                "SELECT COUNT(*) FROM document_requests WHERE org_id = ? AND status = 'open'"
                " AND due_date < date('now')", (g.org["id"],)).fetchone()[0]
        return {
            "languages": languages.all_languages(),
            "status_labels": models.STATUS_LABELS,
            "pending_messages": pending,
            "overdue_count": overdue,
            "provider_name": messaging.get_provider().name,
            "today": date.today().isoformat(),
        }

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = models.authenticate(get_conn(), request.form.get("username", "").strip(),
                                       request.form.get("password", ""))
            if user:
                session.clear()
                session["user_id"] = user["id"]
                models.log_action(get_conn(), user["org_id"], user["id"], "login")
                return redirect(request.args.get("next") or url_for("dashboard"))
            flash("Username or password is incorrect.", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    @app.route("/")
    @login_required
    def dashboard():
        conn = get_conn()
        org_id = g.org["id"]
        return render_template(
            "dashboard.html",
            metrics=models.dashboard_metrics(conn, org_id),
            chase_list=models.list_requests(conn, org_id, "overdue", limit=10),
            due_soon=models.list_requests(conn, org_id, "due_soon", limit=10),
            replies=models.unanswered_inbound(conn, org_id, limit=5))

    # ------------------------------------------------------------------
    # Participants
    # ------------------------------------------------------------------

    @app.route("/participants")
    @login_required
    def participants():
        conn = get_conn()
        rows = models.list_contacts(
            conn, g.org["id"], query=request.args.get("q") or None,
            language=request.args.get("language") or None,
            include_archived=request.args.get("archived") == "1")
        reach = {}
        for row in rows:
            reach[row["id"]] = messaging.reachability(row)
        return render_template("participants.html", participants=rows, reach=reach,
                               q=request.args.get("q", ""),
                               language=request.args.get("language", ""))

    @app.route("/participants/new", methods=["GET", "POST"])
    @login_required
    def participant_new():
        if request.method == "POST":
            errors = _validate_contact(request.form)
            if errors:
                for message in errors:
                    flash(message, "error")
                return render_template("participant_form.html", participant=request.form,
                                       action="new")
            contact_id = models.create_contact(get_conn(), g.org["id"], request.form.to_dict())
            models.log_action(get_conn(), g.org["id"], g.user["id"], "participant.create",
                              "contact %d" % contact_id)
            flash("Participant added.", "success")
            return redirect(url_for("participant_detail", contact_id=contact_id))
        return render_template("participant_form.html", participant={}, action="new")

    @app.route("/participants/<int:contact_id>")
    @login_required
    def participant_detail(contact_id):
        conn = get_conn()
        contact = models.get_contact(conn, g.org["id"], contact_id)
        if not contact:
            abort(404)
        ok, reason = messaging.reachability(contact)
        return render_template(
            "participant_detail.html", participant=contact, reachable=ok, reason=reason,
            requests=models.list_requests(conn, g.org["id"], "all", contact_id=contact_id),
            thread=models.contact_thread(conn, contact_id),
            templates=models.list_templates(conn, g.org["id"]),
            document_types=models.list_document_types(conn, g.org["id"]),
            default_due=models.default_due_date())

    @app.route("/participants/<int:contact_id>/edit", methods=["GET", "POST"])
    @login_required
    def participant_edit(contact_id):
        conn = get_conn()
        contact = models.get_contact(conn, g.org["id"], contact_id)
        if not contact:
            abort(404)
        if request.method == "POST":
            errors = _validate_contact(request.form)
            if errors:
                for message in errors:
                    flash(message, "error")
                return render_template("participant_form.html", participant=request.form,
                                       action="edit", contact_id=contact_id)
            data = request.form.to_dict()
            data["active"] = 1 if request.form.get("active") else 0
            models.update_contact(conn, g.org["id"], contact_id, data)
            models.log_action(conn, g.org["id"], g.user["id"], "participant.update",
                              "contact %d" % contact_id)
            flash("Participant updated.", "success")
            return redirect(url_for("participant_detail", contact_id=contact_id))
        return render_template("participant_form.html", participant=contact, action="edit",
                               contact_id=contact_id)

    @app.route("/participants/<int:contact_id>/opt-out", methods=["POST"])
    @login_required
    def participant_opt_out(contact_id):
        opted_out = request.form.get("opted_out") == "1"
        models.set_opt_out(get_conn(), g.org["id"], contact_id, opted_out)
        models.log_action(get_conn(), g.org["id"], g.user["id"],
                          "participant.opt_out" if opted_out else "participant.opt_in",
                          "contact %d" % contact_id)
        flash("Opt-out recorded. Queued messages were canceled." if opted_out
              else "Participant re-subscribed.", "success")
        return redirect(url_for("participant_detail", contact_id=contact_id))

    @app.route("/participants/<int:contact_id>/message", methods=["POST"])
    @login_required
    def participant_message(contact_id):
        conn = get_conn()
        contact = models.get_contact(conn, g.org["id"], contact_id)
        if not contact:
            abort(404)
        body, language = _compose(conn, contact, request.form)
        if not body:
            flash("Nothing to send -- pick a template or type a message.", "error")
            return redirect(url_for("participant_detail", contact_id=contact_id))
        try:
            messaging.queue_message(conn, g.org, contact, body, language=language,
                                    template_code=request.form.get("template_code") or None,
                                    created_by=g.user["id"])
        except messaging.Blocked as blocked:
            flash("Not sent: %s." % blocked, "error")
            return redirect(url_for("participant_detail", contact_id=contact_id))
        sent, failed = messaging.dispatch_due(conn, g.org["id"])
        models.log_action(conn, g.org["id"], g.user["id"], "message.send",
                          "contact %d" % contact_id)
        flash("Message sent." if sent else
              "Message queued -- it is inside quiet hours and will go out at %d:00."
              % g.org["quiet_end"], "success" if sent else "info")
        if failed:
            flash("%d message failed to send. See the message log." % failed, "error")
        return redirect(url_for("participant_detail", contact_id=contact_id))

    def _compose(conn, contact, form):
        """Resolve a send form into (body, language)."""
        template_code = form.get("template_code")
        if template_code:
            language, body = messaging.pick_variant(
                conn, template_code, contact["org_id"], contact["preferred_language"])
            if not body:
                return None, None
            context = {"first_name": contact["first_name"], "last_name": contact["last_name"],
                       "org_name": g.org["name"]}
            request_id = form.get("request_id")
            if request_id:
                doc_request = models.get_request(conn, g.org["id"], int(request_id))
                if doc_request:
                    subject = nudges.subject_for("document_request")
                    row = {"id": doc_request["id"], "contact_id": doc_request["contact_id"],
                           "target_date": doc_request["due_date"],
                           "document_type_id": doc_request["document_type_id"],
                           "document_name": doc_request["document_name"]}
                    context = subject.context(conn, row, contact, g.org)
            return messaging.render(body, context), language
        body = (form.get("body") or "").strip()
        return (body or None), contact["preferred_language"]

    # ------------------------------------------------------------------
    # Document requests
    # ------------------------------------------------------------------

    @app.route("/requests")
    @login_required
    def requests_list():
        scope = request.args.get("scope", "open")
        rows = models.list_requests(get_conn(), g.org["id"], scope)
        return render_template("requests.html", requests=rows, scope=scope)

    @app.route("/requests/new", methods=["GET", "POST"])
    @login_required
    def request_new():
        conn = get_conn()
        if request.method == "POST":
            contact_id = int(request.form["contact_id"])
            due_date = request.form.get("due_date") or models.default_due_date()
            type_ids = request.form.getlist("document_type_id")
            if not type_ids:
                flash("Pick at least one document.", "error")
                return redirect(url_for("request_new", contact_id=contact_id))
            created = [models.create_request(conn, g.org["id"], contact_id, int(type_id),
                                             due_date, requested_by=g.user["id"],
                                             notes=request.form.get("notes"))
                       for type_id in type_ids]
            models.log_action(conn, g.org["id"], g.user["id"], "request.create",
                              "%d request(s) for contact %d" % (len(created), contact_id))

            if request.form.get("send_now"):
                contact = models.get_contact(conn, g.org["id"], contact_id)
                queued = _send_initial_requests(conn, contact, created)
                flash("%d request(s) created, %d text(s) sent." % (len(created), queued),
                      "success")
            else:
                flash("%d request(s) created." % len(created), "success")
            return redirect(url_for("participant_detail", contact_id=contact_id))

        return render_template(
            "request_form.html",
            participants=models.list_contacts(conn, g.org["id"]),
            document_types=models.list_document_types(conn, g.org["id"]),
            selected_contact=request.args.get("contact_id", type=int),
            default_due=models.default_due_date())

    def _send_initial_requests(conn, contact, request_ids):
        """Text the participant one 'we need this' message per new request."""
        ok, _reason = messaging.reachability(contact)
        if not ok:
            return 0
        subject = nudges.subject_for("document_request")
        queued = 0
        for request_id in request_ids:
            doc_request = models.get_request(conn, g.org["id"], request_id)
            language, body = messaging.pick_variant(
                conn, "doc_request_new", g.org["id"], contact["preferred_language"])
            if not body:
                continue
            row = {"id": doc_request["id"], "contact_id": contact["id"],
                   "target_date": doc_request["due_date"],
                   "document_type_id": doc_request["document_type_id"],
                   "document_name": doc_request["document_name"]}
            messaging.queue_message(
                conn, g.org, contact, messaging.render(body, subject.context(conn, row, contact, g.org)),
                language=language, template_code="doc_request_new",
                subject_type="document_request", subject_id=request_id,
                created_by=g.user["id"])
            queued += 1
        messaging.dispatch_due(conn, g.org["id"])
        return queued

    @app.route("/requests/<int:request_id>/status", methods=["POST"])
    @login_required
    def request_status(request_id):
        conn = get_conn()
        doc_request = models.get_request(conn, g.org["id"], request_id)
        if not doc_request:
            abort(404)
        status = request.form.get("status", "open")
        models.set_request_status(conn, g.org["id"], request_id, status)
        models.log_action(conn, g.org["id"], g.user["id"], "request.status",
                          "request %d -> %s" % (request_id, status))

        if status in models.COMPLETED_STATUSES and request.form.get("thank_them"):
            contact = models.get_contact(conn, g.org["id"], doc_request["contact_id"])
            ok, _reason = messaging.reachability(contact)
            language, body = messaging.pick_variant(
                conn, "doc_received_thanks", g.org["id"], contact["preferred_language"])
            if ok and body:
                subject = nudges.subject_for("document_request")
                row = {"id": request_id, "contact_id": contact["id"],
                       "target_date": doc_request["due_date"],
                       "document_type_id": doc_request["document_type_id"],
                       "document_name": doc_request["document_name"]}
                messaging.queue_message(
                    conn, g.org, contact,
                    messaging.render(body, subject.context(conn, row, contact, g.org)),
                    language=language, template_code="doc_received_thanks",
                    created_by=g.user["id"])
                messaging.dispatch_due(conn, g.org["id"])
        flash("Marked %s." % models.STATUS_LABELS[status].lower(), "success")
        return redirect(request.form.get("next") or url_for("requests_list"))

    @app.route("/requests/<int:request_id>/nudge", methods=["POST"])
    @login_required
    def request_nudge(request_id):
        """One-click chase from the dashboard or request list."""
        conn = get_conn()
        doc_request = models.get_request(conn, g.org["id"], request_id)
        if not doc_request:
            abort(404)
        contact = models.get_contact(conn, g.org["id"], doc_request["contact_id"])
        days_until = (datetime.strptime(doc_request["due_date"], "%Y-%m-%d").date()
                      - date.today()).days
        code = "doc_reminder_before" if days_until > 0 else (
            "doc_due_today" if days_until == 0 else "doc_overdue")
        language, body = messaging.pick_variant(conn, code, g.org["id"],
                                                contact["preferred_language"])
        if not body:
            flash("Template '%s' has no text yet." % code, "error")
            return redirect(request.form.get("next") or url_for("requests_list"))
        subject = nudges.subject_for("document_request")
        row = {"id": request_id, "contact_id": contact["id"],
               "target_date": doc_request["due_date"],
               "document_type_id": doc_request["document_type_id"],
               "document_name": doc_request["document_name"]}
        try:
            messaging.queue_message(
                conn, g.org, contact,
                messaging.render(body, subject.context(conn, row, contact, g.org)),
                language=language, template_code=code, subject_type="document_request",
                subject_id=request_id, created_by=g.user["id"])
        except messaging.Blocked as blocked:
            flash("Not sent to %s: %s." % (contact["first_name"], blocked), "error")
            return redirect(request.form.get("next") or url_for("requests_list"))
        messaging.dispatch_due(conn, g.org["id"])
        flash("Reminder sent to %s in %s." % (contact["first_name"],
                                              languages.name_for(language)), "success")
        return redirect(request.form.get("next") or url_for("requests_list"))

    # ------------------------------------------------------------------
    # Templates and document types
    # ------------------------------------------------------------------

    @app.route("/templates")
    @login_required
    def templates_list():
        conn = get_conn()
        rows = models.list_templates(conn, g.org["id"])
        coverage = {row["id"]: models.translated_language_count(conn, row["id"]) for row in rows}
        return render_template("templates.html", templates=rows, coverage=coverage,
                               total_languages=len(languages.all_languages()))

    @app.route("/templates/new", methods=["GET", "POST"])
    @login_required
    def template_new():
        if request.method == "POST":
            code = (request.form.get("code") or "").strip()
            name = (request.form.get("name") or "").strip()
            if not code or not name:
                flash("A template needs both a code and a name.", "error")
            elif models.get_template_by_code(get_conn(), g.org["id"], code):
                flash("That code is already in use.", "error")
            else:
                template_id = models.create_template(
                    get_conn(), g.org["id"], code, name,
                    request.form.get("category", "document_request"))
                return redirect(url_for("template_edit", template_id=template_id))
        return render_template("template_form.html")

    @app.route("/templates/<int:template_id>", methods=["GET", "POST"])
    @login_required
    def template_edit(template_id):
        conn = get_conn()
        template = models.get_template(conn, g.org["id"], template_id)
        if not template:
            abort(404)
        if request.method == "POST":
            models.save_variants(conn, template_id,
                                 {code: request.form.get("body_%s" % code, "")
                                  for code in languages.codes()})
            models.log_action(conn, g.org["id"], g.user["id"], "template.update",
                              template["code"])
            flash("Template saved.", "success")
            return redirect(url_for("template_edit", template_id=template_id))

        variants = models.template_variants(conn, template_id)
        sample = nudges.preview_context(
            "document_request" if template["category"] == "document_request" else template["category"])
        sample["org_name"] = g.org["name"]
        previews, stats = {}, {}
        for code, body in variants.items():
            previews[code] = messaging.render(body, sample)
            stats[code] = messaging.segment_info(previews[code])
            stats[code]["non_gsm"] = messaging.non_gsm_characters(previews[code])
        return render_template("template_edit.html", template=template, variants=variants,
                               previews=previews, stats=stats,
                               fields=sorted(sample.keys()))

    @app.route("/document-types", methods=["GET", "POST"])
    @login_required
    def document_types():
        conn = get_conn()
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            if name:
                models.create_document_type(conn, g.org["id"], name,
                                            request.form.get("description"))
                flash("Document added.", "success")
            return redirect(url_for("document_types"))
        return render_template("document_types.html",
                               document_types=models.list_document_types(
                                   conn, g.org["id"], include_inactive=True),
                               coverage=models.document_name_coverage(conn, g.org["id"]),
                               total_languages=len(languages.all_languages()) - 1)

    @app.route("/document-types/<int:type_id>/names", methods=["GET", "POST"])
    @login_required
    def document_type_names(type_id):
        conn = get_conn()
        document = conn.execute(
            "SELECT * FROM document_types WHERE id = ? AND org_id = ?",
            (type_id, g.org["id"])).fetchone()
        if not document:
            abort(404)
        if request.method == "POST":
            models.save_document_type_names(
                conn, type_id, {code: request.form.get("name_%s" % code, "")
                                for code in languages.codes() if code != "en"})
            models.log_action(conn, g.org["id"], g.user["id"], "document_type.translate",
                              document["name"])
            flash("Translations saved.", "success")
            return redirect(url_for("document_types"))
        return render_template("document_type_names.html", document=document,
                               names=models.document_type_names(conn, type_id))

    @app.route("/document-types/<int:type_id>/toggle", methods=["POST"])
    @login_required
    def document_type_toggle(type_id):
        models.set_document_type_active(get_conn(), g.org["id"], type_id,
                                        request.form.get("active") == "1")
        return redirect(url_for("document_types"))

    # ------------------------------------------------------------------
    # Reminder rules
    # ------------------------------------------------------------------

    @app.route("/reminders")
    @login_required
    def reminders():
        conn = get_conn()
        return render_template(
            "reminders.html", rules=nudges.list_rules(conn, g.org["id"]),
            templates=models.list_templates(conn, g.org["id"]),
            preview=nudges.run(conn, g.org["id"], dry_run=True),
            describe=nudges.describe_offset)

    @app.route("/reminders/new", methods=["POST"])
    @login_required
    def reminder_new():
        try:
            offset = int(request.form.get("offset_days", 0))
        except ValueError:
            flash("Offset must be a whole number of days.", "error")
            return redirect(url_for("reminders"))
        nudges.create_rule(get_conn(), g.org["id"], request.form.get("name") or "Reminder",
                           request.form["template_code"], offset)
        flash("Reminder rule added.", "success")
        return redirect(url_for("reminders"))

    @app.route("/reminders/<int:rule_id>/toggle", methods=["POST"])
    @login_required
    def reminder_toggle(rule_id):
        nudges.set_rule_active(get_conn(), g.org["id"], rule_id,
                               request.form.get("active") == "1")
        return redirect(url_for("reminders"))

    @app.route("/reminders/run", methods=["POST"])
    @login_required
    def reminders_run():
        conn = get_conn()
        results = nudges.run(conn, g.org["id"])
        queued = sum(1 for row in results if row["status"] == "queued")
        skipped = [row for row in results if row["status"] == "skipped"]
        sent, failed = messaging.dispatch_due(conn, g.org["id"])
        models.log_action(conn, g.org["id"], g.user["id"], "reminders.run",
                          "%d queued, %d sent, %d skipped" % (queued, sent, len(skipped)))
        flash("%d reminder(s) queued, %d sent." % (queued, sent), "success")
        for row in skipped:
            flash("Skipped %s: %s" % (row["contact"], row["reason"]), "info")
        if failed:
            flash("%d message(s) failed. See the message log." % failed, "error")
        return redirect(url_for("reminders"))

    # ------------------------------------------------------------------
    # Message log and inbound
    # ------------------------------------------------------------------

    @app.route("/messages")
    @login_required
    def message_log():
        conn = get_conn()
        return render_template(
            "messages.html",
            messages=models.message_log(conn, g.org["id"],
                                        direction=request.args.get("direction") or None,
                                        status=request.args.get("status") or None),
            direction=request.args.get("direction", ""),
            status=request.args.get("status", ""),
            replies=models.unanswered_inbound(conn, g.org["id"]))

    @app.route("/messages/dispatch", methods=["POST"])
    @login_required
    def messages_dispatch():
        sent, failed = messaging.dispatch_due(get_conn(), g.org["id"])
        flash("%d sent, %d failed." % (sent, failed), "success" if not failed else "error")
        return redirect(url_for("message_log"))

    @app.route("/sms/inbound", methods=["POST"])
    def sms_inbound():
        """Carrier webhook. Twilio posts From/Body; other providers can be mapped here.

        Deliberately unauthenticated at the app layer -- point the carrier at a
        secret path or put it behind the provider's signature validation before
        going live with real numbers.
        """
        from_phone = request.form.get("From") or request.form.get("from")
        body = request.form.get("Body") or request.form.get("body")
        message_id, intent, _contact = messaging.receive_inbound(get_conn(), from_phone, body)
        if message_id is None:
            return ("unknown sender", 404)
        return ("<Response></Response>" if intent != "help" else
                "<Response><Message>Reply STOP to stop texts. Call your case manager for "
                "help.</Message></Response>"), 200, {"Content-Type": "application/xml"}

    @app.route("/jobs/run", methods=["POST"])
    def jobs_run():
        """Run reminder rules and dispatch, triggered by an external scheduler.

        Enabled only when DOORWAY_JOB_TOKEN is set; the caller must present it
        in the X-Doorway-Job-Token header. This exists because some hosts
        (Railway among them) attach a persistent volume to exactly one service,
        so a separate cron service cannot reach the database file -- it calls
        this instead. On a plain server, cron running `jobs.py run` is simpler.
        """
        expected = os.environ.get("DOORWAY_JOB_TOKEN")
        if not expected:
            abort(404)
        presented = request.headers.get("X-Doorway-Job-Token", "")
        if not hmac.compare_digest(presented, expected):
            abort(403)

        conn = get_conn()
        summary = []
        for row in conn.execute("SELECT id, name FROM organizations ORDER BY id"):
            results = nudges.run(conn, row["id"])
            queued = sum(1 for item in results if item["status"] == "queued")
            skipped = [item for item in results if item["status"] == "skipped"]
            sent, failed = messaging.dispatch_due(conn, row["id"])
            models.log_action(conn, row["id"], None, "jobs.run",
                              "%d queued, %d sent, %d failed, %d skipped"
                              % (queued, sent, failed, len(skipped)))
            summary.append({"org_id": row["id"], "org": row["name"], "queued": queued,
                            "sent": sent, "failed": failed,
                            "skipped": [item["reason"] for item in skipped]})
        return jsonify({"ran_at": db.now_str(), "organizations": summary})

    @app.route("/simulate/inbound", methods=["POST"])
    @login_required
    def simulate_inbound():
        """Demo aid: pretend a participant texted back. Console provider only."""
        if messaging.get_provider().name != "console":
            abort(403)
        conn = get_conn()
        contact = models.get_contact(conn, g.org["id"], int(request.form["contact_id"]))
        if not contact:
            abort(404)
        _message_id, intent, _row = messaging.receive_inbound(
            conn, contact["phone"], request.form.get("body", ""))
        flash("Simulated inbound reply (%s)." % intent, "info")
        return redirect(url_for("participant_detail", contact_id=contact["id"]))

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        conn = get_conn()
        if request.method == "POST":
            if g.user["role"] != "admin":
                abort(403)
            models.update_org(conn, g.org["id"], request.form.get("name") or g.org["name"],
                              request.form.get("timezone") or g.org["timezone"],
                              int(request.form.get("quiet_start", 21)),
                              int(request.form.get("quiet_end", 8)),
                              request.form.get("sms_from") or None)
            models.log_action(conn, g.org["id"], g.user["id"], "settings.update")
            flash("Settings saved.", "success")
            return redirect(url_for("settings"))
        return render_template("settings.html", audit=models.recent_audit(conn, g.org["id"]))

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403,
                               message="You do not have access to that."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="Page not found."), 404

    return app


def _validate_contact(form):
    errors = []
    if not (form.get("first_name") or "").strip():
        errors.append("First name is required.")
    if not (form.get("last_name") or "").strip():
        errors.append("Last name is required.")
    phone = messaging.normalize_phone(form.get("phone"))
    if form.get("phone") and (not phone or len(phone) < 11):
        errors.append("That phone number does not look like a mobile number.")
    if form.get("consent_sms") and not phone:
        errors.append("SMS consent needs a phone number on file.")
    if form.get("preferred_language") and not languages.is_supported(
            form.get("preferred_language")):
        errors.append("Unsupported language.")
    return errors


app = create_app()

if __name__ == "__main__":
    # Local development only. In production Doorway runs under gunicorn via
    # wsgi.py -- see README.md.
    app.run(debug=True, host="127.0.0.1", port=5000)
