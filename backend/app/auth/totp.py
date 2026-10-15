"""TOTP second factor (RFC 6238): 6-digit codes from an authenticator app."""

import base64
import binascii
import hmac
import re
import time

import pyotp

STEP_SECONDS = 30
_CODE = re.compile(r"\d{6}")


def is_valid_secret(secret: str) -> bool:
    """Base32 secret of at least 128 bits (pyotp.random_base32() gives 160)."""
    cleaned = secret.strip().upper()
    try:
        decoded = base64.b32decode(cleaned + "=" * (-len(cleaned) % 8))
    except binascii.Error:
        return False
    return len(decoded) >= 16


def verify_code(
    secret: str, code: str, last_step: int | None, now: float | None = None
) -> int | None:
    """Return the time step matched by `code`, or None if the code is refused.

    One step of clock drift is tolerated on each side. A step at or before
    `last_step` is refused, so a code that was already used cannot be replayed.
    """
    if not _CODE.fullmatch(code):
        return None
    totp = pyotp.TOTP(secret.strip().upper(), interval=STEP_SECONDS)
    current = int((time.time() if now is None else now) // STEP_SECONDS)
    for step in (current - 1, current, current + 1):
        if hmac.compare_digest(totp.generate_otp(step), code) and (
            last_step is None or step > last_step
        ):
            return step
    return None


def provisioning_uri(secret: str, account: str) -> str:
    return pyotp.TOTP(secret, interval=STEP_SECONDS).provisioning_uri(
        name=account, issuer_name="Jarvis"
    )
