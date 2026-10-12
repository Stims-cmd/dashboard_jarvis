"""Reads a Leboncoin alert email: authenticity check, then the ads it lists.

Only emails whose DKIM signature was verified for leboncoin.fr by the receiving
server are accepted: anyone can send a fake "alert" to the mailbox.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

TRUSTED_DOMAIN = "leboncoin.fr"
# "dkim=pass ... header.d=leboncoin.fr" inside an Authentication-Results header.
# Gmail writes "header.i=@leboncoin.fr" instead (the signing identity, which must be
# the signing domain or one of its subdomains): both forms are read.
_DKIM_PASS = re.compile(
    r"\bdkim=pass\b[^;]*?\bheader\.[di]=(?:[^@\s;]*@)?([A-Za-z0-9.-]+)", re.IGNORECASE
)


@dataclass(frozen=True)
class AdData:
    ad_id: str
    title: str
    price_cents: int | None
    location: str
    url: str


@dataclass(frozen=True)
class Alert:
    search_name: str
    received_at: datetime | None
    ads: list[AdData]


def _is_trusted(domain: str) -> bool:
    domain = domain.lower().rstrip(".")
    return domain == TRUSTED_DOMAIN or domain.endswith("." + TRUSTED_DOMAIN)


def is_authentic(message: EmailMessage) -> bool:
    """True when the receiving server verified a leboncoin.fr DKIM signature.

    Only the topmost Authentication-Results header counts: it is the one added by
    our own mail provider. Lower ones may have been written by the sender.
    """
    results = message.get_all("Authentication-Results") or []
    if not results:
        return False
    signed = any(_is_trusted(domain) for domain in _DKIM_PASS.findall(str(results[0])))
    sender = message.get("From")
    sender_domain = sender.addresses[0].domain if sender and sender.addresses else ""
    return signed and _is_trusted(sender_domain)


def _received_at(message: EmailMessage) -> datetime | None:
    try:
        return parsedate_to_datetime(str(message["Date"]))
    except (TypeError, ValueError):
        return None


def extract_ads(html: str) -> list[AdData]:
    """Ads listed in the HTML body of an alert.

    Waiting for real alert emails: their HTML layout is not publicly documented,
    so the extraction is written against recorded samples, not guessed.
    """
    raise NotImplementedError("alert layout not known yet")


def parse_alert(raw: bytes) -> Alert | None:
    """The alert, or None when the email is not an authentic Leboncoin alert."""
    message = message_from_bytes(raw, policy=policy.default)
    if not isinstance(message, EmailMessage) or not is_authentic(message):
        return None
    body = message.get_body(preferencelist=("html",))
    if body is None:
        return None
    return Alert(
        search_name=str(message.get("Subject", "")).strip()[:200],
        received_at=_received_at(message),
        ads=extract_ads(body.get_content()),
    )
