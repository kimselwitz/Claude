# -*- coding: utf-8 -*-
"""
Starter content and demo data.

The message translations below are starter text, not certified translations.
Language access is a legal obligation (HUD LEP guidance), so an agency should
have its own interpreter review each variant before a pilot goes live -- the
template editor exists precisely so they can edit them in place.
"""
from datetime import date, timedelta

import db
import models
import nudges

STARTER_TEMPLATES = [
    {
        "code": "doc_request_new",
        "name": "New document request",
        "category": "document_request",
        "bodies": {
            "en": "{{org_name}}: Hi {{first_name}}, we need your {{document_name}} by "
                  "{{due_date}} to keep your application moving. Reply to this text with a "
                  "photo, or call us with questions. Reply STOP to opt out.",
            "es": "{{org_name}}: Hola {{first_name}}, necesitamos su {{document_name}} antes "
                  "del {{due_date}} para continuar con su solicitud. Responda a este mensaje "
                  "con una foto o llámenos si tiene preguntas. Responda STOP para no recibir "
                  "más mensajes.",
            "fr": "{{org_name}} : Bonjour {{first_name}}, nous avons besoin de votre "
                  "{{document_name}} avant le {{due_date}} pour faire avancer votre dossier. "
                  "Répondez à ce message avec une photo ou appelez-nous. Répondez STOP pour "
                  "ne plus recevoir de messages.",
            "pt": "{{org_name}}: Olá {{first_name}}, precisamos do seu {{document_name}} até "
                  "{{due_date}} para dar continuidade ao seu pedido. Responda a esta mensagem "
                  "com uma foto ou ligue-nos. Responda STOP para não receber mais mensagens.",
            "so": "{{org_name}}: Salaan {{first_name}}, waxaan u baahannahay {{document_name}} "
                  "ka hor {{due_date}} si codsigaagu u socdo. Sawir halkan noogu soo dir ama "
                  "na soo wac. U dir STOP haddii aadan doonayn farriimo dheeraad ah.",
            "ar": "{{org_name}}: مرحباً {{first_name}}، نحتاج إلى {{document_name}} قبل "
                  "{{due_date}} حتى نتابع طلبك. أرسل صورة رداً على هذه الرسالة أو اتصل بنا. "
                  "أرسل STOP لإيقاف الرسائل.",
            "ln": "{{org_name}}: Mbote {{first_name}}, tosengeli na {{document_name}} liboso "
                  "ya {{due_date}} mpo demande na yo etambola. Tinda foto na message oyo to "
                  "benga biso. Tinda STOP soki olingi lisusu message te.",
        },
    },
    {
        "code": "doc_reminder_before",
        "name": "Reminder before due date",
        "category": "document_request",
        "bodies": {
            "en": "{{org_name}}: Hi {{first_name}}, a reminder that your {{document_name}} is "
                  "due in {{days_until_due}} days ({{due_date}}). A clear photo texted back to "
                  "this number works.",
            "es": "{{org_name}}: Hola {{first_name}}, le recordamos que su {{document_name}} "
                  "vence en {{days_until_due}} días ({{due_date}}). Puede enviar una foto clara "
                  "a este número.",
            "fr": "{{org_name}} : Bonjour {{first_name}}, rappel : votre {{document_name}} est "
                  "attendu dans {{days_until_due}} jours ({{due_date}}). Une photo nette envoyée "
                  "à ce numéro suffit.",
            "pt": "{{org_name}}: Olá {{first_name}}, lembrete: o seu {{document_name}} vence em "
                  "{{days_until_due}} dias ({{due_date}}). Uma foto nítida enviada para este "
                  "número é suficiente.",
            "so": "{{org_name}}: Salaan {{first_name}}, xasuusin: {{document_name}} waxaa la "
                  "rabaa {{days_until_due}} maalmood gudahood ({{due_date}}). Sawir cad oo "
                  "lambarkan loo soo diro way ku filan tahay.",
            "ar": "{{org_name}}: مرحباً {{first_name}}، تذكير: {{document_name}} مطلوب خلال "
                  "{{days_until_due}} أيام ({{due_date}}). تكفي صورة واضحة تُرسل إلى هذا الرقم.",
            "ln": "{{org_name}}: Mbote {{first_name}}, bokundoli: {{document_name}} esengeli na "
                  "mikolo {{days_until_due}} ({{due_date}}). Okoki kotinda foto na nimero oyo.",
        },
    },
    {
        "code": "doc_due_today",
        "name": "Due today",
        "category": "document_request",
        "bodies": {
            "en": "{{org_name}}: Hi {{first_name}}, your {{document_name}} is due today. Text a "
                  "photo to this number, or reply here if you need more time.",
            "es": "{{org_name}}: Hola {{first_name}}, su {{document_name}} vence hoy. Envíe una "
                  "foto a este número o responda aquí si necesita más tiempo.",
            "fr": "{{org_name}} : Bonjour {{first_name}}, votre {{document_name}} est attendu "
                  "aujourd'hui. Envoyez une photo à ce numéro ou répondez ici s'il vous faut "
                  "plus de temps.",
            "pt": "{{org_name}}: Olá {{first_name}}, o seu {{document_name}} vence hoje. Envie "
                  "uma foto para este número ou responda aqui se precisar de mais tempo.",
            "so": "{{org_name}}: Salaan {{first_name}}, {{document_name}} maanta ayaa la rabaa. "
                  "Sawir u soo dir lambarkan ama halkan ka soo jawaab haddii aad waqti dheeraad "
                  "ah u baahan tahay.",
            "ar": "{{org_name}}: مرحباً {{first_name}}، {{document_name}} مطلوب اليوم. أرسل صورة "
                  "إلى هذا الرقم أو ردّ هنا إذا كنت بحاجة إلى وقت إضافي.",
            "ln": "{{org_name}}: Mbote {{first_name}}, {{document_name}} esengeli lelo. Tinda "
                  "foto na nimero oyo to zongisa awa soki osengeli na ntango mosusu.",
        },
    },
    {
        "code": "doc_overdue",
        "name": "Past due follow-up",
        "category": "document_request",
        "bodies": {
            "en": "{{org_name}}: Hi {{first_name}}, we still need your {{document_name}} "
                  "({{days_overdue}} days past due). Reply here if something is in the way -- "
                  "we would rather help than close your file.",
            "es": "{{org_name}}: Hola {{first_name}}, todavía necesitamos su {{document_name}} "
                  "({{days_overdue}} días de retraso). Responda si hay algún problema: "
                  "preferimos ayudarle antes que cerrar su caso.",
            "fr": "{{org_name}} : Bonjour {{first_name}}, il nous manque toujours votre "
                  "{{document_name}} ({{days_overdue}} jours de retard). Répondez-nous si "
                  "quelque chose bloque : nous préférons vous aider que fermer votre dossier.",
            "pt": "{{org_name}}: Olá {{first_name}}, ainda precisamos do seu {{document_name}} "
                  "({{days_overdue}} dias de atraso). Responda se houver algum problema: "
                  "preferimos ajudar a fechar o seu processo.",
            "so": "{{org_name}}: Salaan {{first_name}}, wali waxaan u baahannahay "
                  "{{document_name}} ({{days_overdue}} maalmood ayuu daahay). Noo soo jawaab "
                  "haddii caqabad jirto -- waxaan doorbidaynaa inaan ku caawinno.",
            "ar": "{{org_name}}: مرحباً {{first_name}}، ما زلنا بحاجة إلى {{document_name}} "
                  "(تأخر {{days_overdue}} أيام). ردّ علينا إذا كان هناك ما يعيقك، فنحن نفضل "
                  "مساعدتك على إغلاق ملفك.",
            "ln": "{{org_name}}: Mbote {{first_name}}, tozali naino kozela {{document_name}} "
                  "(mikolo {{days_overdue}} eleki). Zongisa soki ezali na mokakatano -- tolingi "
                  "kosalisa yo.",
        },
    },
    {
        "code": "doc_received_thanks",
        "name": "Received - thank you",
        "category": "document_request",
        "bodies": {
            "en": "{{org_name}}: Thank you {{first_name}} -- we received your "
                  "{{document_name}}. Nothing more is needed from you right now.",
            "es": "{{org_name}}: Gracias {{first_name}}, recibimos su {{document_name}}. Por "
                  "ahora no necesita hacer nada más.",
            "fr": "{{org_name}} : Merci {{first_name}}, nous avons bien reçu votre "
                  "{{document_name}}. Rien d'autre n'est nécessaire pour le moment.",
            "pt": "{{org_name}}: Obrigado {{first_name}}, recebemos o seu {{document_name}}. Por "
                  "agora não precisa de fazer mais nada.",
            "so": "{{org_name}}: Mahadsanid {{first_name}}, waan helnay {{document_name}}. Hadda "
                  "wax kale looma baahna.",
            "ar": "{{org_name}}: شكراً {{first_name}}، استلمنا {{document_name}}. لا حاجة إلى "
                  "شيء آخر الآن.",
            "ln": "{{org_name}}: Matondi {{first_name}}, tozwi {{document_name}}. Sikoyo eloko "
                  "mosusu esengeli te.",
        },
    },
]

# (English name, description, {language: translated name}). The translated name
# is what gets substituted into {{document_name}} for that participant.
STARTER_DOCUMENT_TYPES = [
    ("Photo ID", "Driver's license, state ID, or passport for each adult", {
        "es": "Identificaci\u00f3n con foto",
        "fr": "Pi\u00e8ce d'identit\u00e9 avec photo",
        "pt": "Documento de identifica\u00e7\u00e3o com foto",
        "so": "Aqoonsi sawir leh",
        "ar": "\u0628\u0637\u0627\u0642\u0629 \u0647\u0648\u064a\u0629 \u0628\u0635\u0648\u0631\u0629",
        "ln": "Karte ya identit\u00e9 na foto"}),
    ("Social Security card", "Card or SSA award letter showing the number", {
        "es": "Tarjeta de Seguro Social",
        "fr": "Carte de s\u00e9curit\u00e9 sociale",
        "pt": "Cart\u00e3o de Seguran\u00e7a Social",
        "so": "Kaarka Social Security",
        "ar": "\u0628\u0637\u0627\u0642\u0629 \u0627\u0644\u0636\u0645\u0627\u0646 \u0627\u0644\u0627\u062c\u062a\u0645\u0627\u0639\u064a",
        "ln": "Karte ya Social Security"}),
    ("Birth certificate", "For each household member under 18", {
        "es": "Acta de nacimiento",
        "fr": "Acte de naissance",
        "pt": "Certid\u00e3o de nascimento",
        "so": "Shahaadada dhalashada",
        "ar": "\u0634\u0647\u0627\u062f\u0629 \u0627\u0644\u0645\u064a\u0644\u0627\u062f",
        "ln": "Atesta ya mbotama"}),
    ("Proof of income", "Four consecutive pay stubs, or an employer letter", {
        "es": "Comprobante de ingresos",
        "fr": "Justificatif de revenus",
        "pt": "Comprovativo de rendimentos",
        "so": "Caddaynta dakhliga",
        "ar": "\u0625\u062b\u0628\u0627\u062a \u0627\u0644\u062f\u062e\u0644",
        "ln": "Elembo ya mbongo ya mosala"}),
    ("Benefit award letter", "SSI/SSDI, TANF, or unemployment award letter", {
        "es": "Carta de concesi\u00f3n de beneficios",
        "fr": "Lettre d'attribution des prestations",
        "pt": "Carta de atribui\u00e7\u00e3o de benef\u00edcios",
        "so": "Warqadda gunnada",
        "ar": "\u062e\u0637\u0627\u0628 \u0645\u0646\u062d \u0627\u0644\u0645\u0633\u0627\u0639\u062f\u0627\u062a",
        "ln": "Mokanda ya lifuti"}),
    ("Bank statement", "Most recent full statement, all pages", {
        "es": "Estado de cuenta bancario",
        "fr": "Relev\u00e9 bancaire",
        "pt": "Extrato banc\u00e1rio",
        "so": "Bayaanka bangiga",
        "ar": "\u0643\u0634\u0641 \u062d\u0633\u0627\u0628 \u0628\u0646\u0643\u064a",
        "ln": "Rapport ya banki"}),
    ("Signed release of information", "Required before we can verify with third parties", {
        "es": "Autorizaci\u00f3n firmada para divulgar informaci\u00f3n",
        "fr": "Autorisation sign\u00e9e de communication d'informations",
        "pt": "Autoriza\u00e7\u00e3o assinada de divulga\u00e7\u00e3o de informa\u00e7\u00e3o",
        "so": "Ogolaansho saxeexan oo macluumaadka la wadaago",
        "ar": "\u0625\u0630\u0646 \u0645\u0648\u0642\u0651\u0639 \u0628\u0627\u0644\u0625\u0641\u0635\u0627\u062d \u0639\u0646 \u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0627\u062a",
        "ln": "Ndingisa esalemi mpo na kopesa basango"}),
    ("Landlord verification", "Contact information for the current or most recent landlord", {
        "es": "Verificaci\u00f3n del arrendador",
        "fr": "Attestation du propri\u00e9taire",
        "pt": "Verifica\u00e7\u00e3o do senhorio",
        "so": "Xaqiijinta milkiilaha guriga",
        "ar": "\u062a\u0623\u0643\u064a\u062f \u0645\u0646 \u0627\u0644\u0645\u0627\u0644\u0643",
        "ln": "Bondimi ya nkolo ndako"}),
]

STARTER_RULES = [
    ("Heads-up 3 days out", "doc_reminder_before", 3),
    ("Due today", "doc_due_today", 0),
    ("Two days past due", "doc_overdue", -2),
    ("One week past due", "doc_overdue", -7),
]


def seed_org(conn, name="Casco Bay Housing Services", kind="nonprofit"):
    cursor = conn.execute(
        "INSERT INTO organizations (name, kind, sms_from) VALUES (?, ?, ?)",
        (name, kind, "+12075550100"))
    conn.commit()
    org_id = cursor.lastrowid

    for name, description, translations in STARTER_DOCUMENT_TYPES:
        type_id = models.create_document_type(conn, org_id, name, description)
        models.save_document_type_names(conn, type_id, translations)

    for spec in STARTER_TEMPLATES:
        template_id = models.create_template(conn, org_id, spec["code"], spec["name"],
                                             spec["category"])
        models.save_variants(conn, template_id, spec["bodies"])

    for rule_name, template_code, offset in STARTER_RULES:
        nudges.create_rule(conn, org_id, rule_name, template_code, offset)

    return org_id


DEMO_PARTICIPANTS = [
    # name, phone, language, program, consent, external ref
    ("Ana", "Reyes", "207-555-0142", "es", "HCV waitlist", 1, "WL-10241"),
    ("Marcus", "Whitfield", "207-555-0118", "en", "TBRA", 1, "TBRA-3312"),
    ("Fatuma", "Abdi", "207-555-0173", "so", "HCV waitlist", 1, "WL-10255"),
    ("Jean-Baptiste", "Mukendi", "207-555-0164", "fr", "Housing counseling", 1, "HC-887"),
    ("Dorothy", "Pelletier", "207-555-0139", "en", "Public housing", 1, "PH-4402"),
    ("Rosa", "Carvalho", "207-555-0156", "pt", "Eviction prevention", 1, "EP-221"),
    ("Samir", "Haddad", "207-555-0187", "ar", "HCV waitlist", 0, "WL-10261"),
    ("Terrence", "Boyd", "207-555-0195", "en", "CoC rapid rehousing", 1, "RRH-77"),
]


def seed_demo(conn, org_id, user_id=None):
    """Populate a believable mid-pilot caseload so the dashboard has something
    to show in a demo. Not called by default."""
    today = date.today()
    document_types = models.list_document_types(conn, org_id)
    by_name = {row["name"]: row["id"] for row in document_types}

    contact_ids = []
    for first, last, phone, language, program, consent, ref in DEMO_PARTICIPANTS:
        contact_ids.append(models.create_contact(conn, org_id, {
            "first_name": first, "last_name": last, "phone": phone,
            "preferred_language": language, "program": program,
            "consent_sms": consent, "external_ref": ref,
        }))

    # A spread of due dates so overdue / due-soon / upcoming all appear.
    plan = [
        (0, "Proof of income", -7, "open"),
        (0, "Photo ID", -30, "verified"),
        (1, "Bank statement", -2, "open"),
        (2, "Signed release of information", 0, "open"),
        (2, "Birth certificate", 6, "open"),
        (3, "Proof of income", 3, "open"),
        (4, "Landlord verification", -14, "open"),
        (4, "Photo ID", -21, "received"),
        (5, "Benefit award letter", 3, "open"),
        (6, "Photo ID", 3, "open"),
        (7, "Social Security card", -2, "open"),
        (7, "Proof of income", -25, "verified"),
    ]
    for index, document_name, offset, status in plan:
        request_id = models.create_request(
            conn, org_id, contact_ids[index], by_name[document_name],
            (today + timedelta(days=offset)).isoformat(), requested_by=user_id)
        # Backdate the request so turnaround metrics are meaningful.
        conn.execute("UPDATE document_requests SET requested_at = ? WHERE id = ?",
                     ((today + timedelta(days=offset - 10)).isoformat() + " 09:00:00", request_id))
        if status != "open":
            conn.execute(
                "UPDATE document_requests SET status = ?, closed_at = ? WHERE id = ?",
                (status, (today + timedelta(days=offset - 4)).isoformat() + " 14:00:00",
                 request_id))
    conn.commit()
    return contact_ids
