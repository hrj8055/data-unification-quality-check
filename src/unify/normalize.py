"""Rules that turn messy values into one standard format."""
from __future__ import annotations

import re

EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")


def clean_text(value) -> str:
    """Strip, collapse inner spaces, treat None/NaN as empty."""
    if value is None:
        return ""
    text = str(value)
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def normalize_name(value) -> str:
    return clean_text(value).title()


def normalize_city(value) -> str:
    city = clean_text(value).title()
    aliases = {"Bangalore": "Bengaluru", "Bombay": "Mumbai", "New Delhi": "Delhi", "Gurgaon": "Gurugram"}
    return aliases.get(city, city)


def normalize_email(value) -> str:
    """Lower-case and trim. Returns '' when the value is not a valid email."""
    email = clean_text(value).lower().replace(" ", "")
    return email if EMAIL_RE.match(email) else ""


def normalize_phone(value) -> str:
    """Return a 10-digit Indian mobile number, or '' if the value can't be one.

    Handles +91, 91-, leading 0, spaces, dashes and brackets.
    """
    digits = re.sub(r"\D", "", clean_text(value))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    return ""


def phone_format(value) -> str:
    """Describe the format a phone number was written in (used to report mixed formats)."""
    text = clean_text(value)
    if not text:
        return "empty"
    if text.startswith("+91"):
        return "+91 prefix"
    if text.startswith("91-") or (text.isdigit() and len(text) == 12):
        return "91 prefix"
    if text.startswith("0"):
        return "leading 0"
    if "(" in text:
        return "brackets"
    if "-" in text:
        return "dashes"
    if " " in text:
        return "spaces"
    return "10 digits"


def name_similarity(a: str, b: str) -> float:
    """Share of name words two names have in common (0 to 1)."""
    wa, wb = set(normalize_name(a).lower().split()), set(normalize_name(b).lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))
