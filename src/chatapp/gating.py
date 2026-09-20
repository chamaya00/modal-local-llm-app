"""Server-side checks that gate access to the model.

Both checks are pure functions of their inputs so they can be tested
without Modal, Gradio, or a real secret in place.
"""

from __future__ import annotations

import hmac


def check_passcode(submitted: str | None, expected: str | None) -> bool:
    """True only if `submitted` matches `expected` exactly.

    Uses a constant-time comparison since this guards a shared secret
    checked on every request. Missing/empty values never match.
    """
    if not submitted or not expected:
        return False
    return hmac.compare_digest(submitted, expected)


def is_paused(flag_value: str | None) -> bool:
    """True if the `APP_PAUSED` secret value means "paused".

    Accepts the case-insensitive string "true"; anything else
    (unset, "false", empty) means the app is live.
    """
    return (flag_value or "").strip().lower() == "true"
