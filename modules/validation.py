"""
validation.py

Input rules shared by user creation and patient registration.
Each *_error() function returns a message if the value is bad, or None if it is fine.
"""

import re

# letters (any language) separated by single spaces, hyphens or apostrophes: "Mary-Jane", "O'Brien"
_NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")

PHONE_DIGITS = 10
MIN_PASSWORD = 8


class ValidationError(ValueError):
    """Raised with every problem found, so the user can fix them all in one go."""

    def __init__(self, errors):
        self.errors = list(errors)
        if len(self.errors) == 1:
            message = self.errors[0]
        else:
            message = "Please fix the following:\n\n" + "\n".join(f"- {e}" for e in self.errors)
        super().__init__(message)


def raise_if_errors(errors):
    errors = [e for e in errors if e]
    if errors:
        raise ValidationError(errors)


def name_error(value, label="Name"):
    v = (value or "").strip()
    if not v:
        return f"{label} is required."
    if len(v) > 50:
        return f"{label} must be 50 characters or fewer."
    if not _NAME_RE.match(v):
        return f"{label} can only contain letters, spaces, hyphens and apostrophes (no numbers)."
    return None


def email_error(value):
    v = (value or "").strip()
    if not v:
        return "Email is required."
    if len(v) > 254 or ".." in v or not _EMAIL_RE.match(v):
        return "Enter a valid email address, for example name@example.com."
    return None


def phone_error(value, required=False):
    v = (value or "").strip()
    if not v:
        return "Phone number is required." if required else None
    if not (v.isascii() and v.isdigit()):
        return "Phone number must contain digits only (no spaces, letters or symbols)."
    if len(v) != PHONE_DIGITS:
        return f"Phone number must be exactly {PHONE_DIGITS} digits."
    return None


def password_error(value):
    v = value or ""
    if len(v) < MIN_PASSWORD:
        return f"Password must be at least {MIN_PASSWORD} characters."
    if not v.strip():
        return "Password cannot be only spaces."
    return None


def text_error(value, label, max_len=200):
    if value and len(value.strip()) > max_len:
        return f"{label} must be {max_len} characters or fewer."
    return None