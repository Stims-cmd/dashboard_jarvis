"""Identifiers to watch, read from data/osint.toml (never committed, never logged).

Only labels (or usernames) are stored in the database: raw emails and phone
numbers stay in this file.
"""

import logging
import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class LabeledValue(BaseModel):
    label: str = Field(min_length=1, max_length=50)
    value: str = Field(min_length=3, max_length=200)


# Restricting usernames keeps them safe to put in API URLs (no "/", "?", "..").
Username = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,49}$")]


class OsintTargets(BaseModel):
    emails: list[LabeledValue] = []
    names: list[Annotated[str, Field(min_length=3, max_length=100)]] = []
    usernames: list[Username] = []
    phones: list[LabeledValue] = []


def load_targets(path: Path) -> OsintTargets | None:
    """Parsed identifiers, or None if the file is missing or invalid."""
    if not path.is_file():
        logger.warning("osint file not found: %s (collection skipped)", path)
        return None
    try:
        return OsintTargets.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        # The error type only: the message could quote an identifier.
        logger.warning("osint file invalid (%s): collection skipped", type(error).__name__)
        return None


def phone_variants(phone: str) -> list[str]:
    """'+33 6 12 34 56 78' -> ['06 12 34 56 78', '+33612345678'] (French numbers)."""
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if digits.startswith("+33"):
        national = "0" + digits[3:]
    elif digits.startswith("0"):
        national = digits
        digits = "+33" + digits[1:]
    else:
        return [phone.strip()]
    spaced = " ".join(national[i : i + 2] for i in range(0, len(national), 2))
    return [spaced, digits]
