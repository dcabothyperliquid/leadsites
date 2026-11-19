"""Small shared helpers for the email flow (stdlib only)."""
import re

_EMAIL = re.compile(r"^[a-z0-9._%+\-]{1,64}@[a-z0-9\-]+(\.[a-z0-9\-]+)*\.[a-z]{2,24}$")
_BAD_TLD = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")
_BAD_DOMAIN = ("example.com", "example.org", "domain.com", "email.com", "test.com", "sentry.io", "wixpress.com")


def clean_email(raw):
    """First valid address from an OSM-style value ('a@x.com;b@y.com'), lower-cased, else ''."""
    for part in re.split(r"[;,\s]+", (raw or "").strip().lower()):
        part = part.strip().removeprefix("mailto:").strip("<>.")
        if not part or not _EMAIL.match(part) or part.endswith(_BAD_TLD):
            continue
        if part.split("@", 1)[1] in _BAD_DOMAIN:
            continue
        return part
    return ""


def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())
