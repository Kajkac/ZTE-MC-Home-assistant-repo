"""Helpers for describing sensitive values in log messages.

Users routinely paste home-assistant.log into bug reports, so session tokens,
auth hashes, phone numbers and SMS bodies must never be logged verbatim.
"""


def redact(value) -> str:
    """Describe a secret (session token, auth hash) without disclosing it.

    The length is kept: it distinguishes "no token" from "token of the wrong
    shape", which is what actually helps when debugging authentication.
    """
    if not value:
        return "<empty>"
    return f"<redacted, {len(str(value))} chars>"


def redact_phone(number) -> str:
    """Mask a phone number, keeping the last two digits for correlation."""
    text = str(number or "")
    if not text:
        return "<empty>"
    if len(text) <= 2:
        return "*" * len(text)
    return "*" * (len(text) - 2) + text[-2:]


def describe_text(text) -> str:
    """Describe a message body by length only; SMS content is never logged."""
    if text is None:
        return "<empty>"
    return f"<{len(str(text))} chars>"
