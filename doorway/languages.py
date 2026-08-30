"""
Language registry for Doorway.

Language access is a first-class feature, not an afterthought: every message
template carries one body per language, and each participant has a preferred
language that selects the variant automatically.

The default set covers the languages most commonly encountered by housing
programs in Maine and northern New England. Agencies can extend the list --
nothing else in the codebase hard-codes a language code.
"""

LANGUAGES = [
    {"code": "en", "name": "English",    "endonym": "English",    "rtl": False},
    {"code": "es", "name": "Spanish",    "endonym": "Espanol",    "rtl": False},
    {"code": "fr", "name": "French",     "endonym": "Francais",   "rtl": False},
    {"code": "pt", "name": "Portuguese", "endonym": "Portugues",  "rtl": False},
    {"code": "so", "name": "Somali",     "endonym": "Soomaali",   "rtl": False},
    {"code": "ar", "name": "Arabic",     "endonym": "al-Arabiya", "rtl": True},
    {"code": "ln", "name": "Lingala",    "endonym": "Lingala",    "rtl": False},
]

DEFAULT_LANGUAGE = "en"

_BY_CODE = {lang["code"]: lang for lang in LANGUAGES}


def all_languages():
    """Every supported language, in display order."""
    return list(LANGUAGES)


def codes():
    return [lang["code"] for lang in LANGUAGES]


def is_supported(code):
    return code in _BY_CODE


def get(code):
    """Look up a language, falling back to the default rather than raising."""
    return _BY_CODE.get(code, _BY_CODE[DEFAULT_LANGUAGE])


def name_for(code):
    return get(code)["name"]


def label_for(code):
    lang = get(code)
    if lang["name"] == lang["endonym"]:
        return lang["name"]
    return "%s (%s)" % (lang["name"], lang["endonym"])
