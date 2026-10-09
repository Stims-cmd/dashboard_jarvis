"""Password verification and session token helpers."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
# Verified when the username is wrong, so both failure paths take the same time.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def check_credentials(
    username: str, password: str, expected_username: str, password_hash: str
) -> bool:
    username_ok = hmac.compare_digest(username.encode(), expected_username.encode())
    try:
        password_ok = _hasher.verify(password_hash if username_ok else _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        password_ok = False
    return username_ok and password_ok


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
