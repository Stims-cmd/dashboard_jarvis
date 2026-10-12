"""Read-only access to the dedicated mailbox receiving the Leboncoin alerts.

The folder is opened read-only and messages are fetched with BODY.PEEK: nothing is
ever marked as read, moved or deleted. The connection uses TLS with certificate
checks. Neither the address nor the password is ever logged.
"""

import imaplib
import re
import ssl
from dataclasses import dataclass
from datetime import date
from email.parser import BytesHeaderParser
from types import TracebackType
from typing import Protocol, Self

from app.config import Settings

# IMAP dates use English month names whatever the server locale ("01-Oct-2026").
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_UID = re.compile(rb"\bUID (\d+)")
TIMEOUT_SECONDS = 30


class Mailbox(Protocol):
    def list_since(self, day: date) -> list[tuple[str, str]]:
        """(uid, Message-ID) of every message received since this day."""
        ...

    def fetch(self, uid: str) -> bytes:
        """Full raw message."""
        ...


@dataclass(frozen=True)
class ImapConfig:
    host: str
    port: int
    username: str
    password: str
    folder: str

    @classmethod
    def from_settings(cls, settings: Settings) -> Self | None:
        if not (
            settings.lbc_imap_host and settings.lbc_imap_username and settings.lbc_imap_password
        ):
            return None
        return cls(
            host=settings.lbc_imap_host,
            port=settings.lbc_imap_port,
            username=settings.lbc_imap_username,
            password=settings.lbc_imap_password.get_secret_value(),
            folder=settings.lbc_imap_folder,
        )


def imap_date(day: date) -> str:
    return f"{day.day:02d}-{_MONTHS[day.month - 1]}-{day.year}"


def quote(value: str) -> str:
    """IMAP quoted string: imaplib does not quote arguments itself."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_header_fetch(data: list) -> list[tuple[str, str]]:
    """Turns the answer of a UID FETCH of the Message-ID header into (uid, Message-ID).

    imaplib returns tuples (b'1 (UID 42 BODY[...] {50}', b'Message-ID: <...>') mixed
    with closing b')' strings. A message without Message-ID gets "uid:<uid>".
    """
    found = []
    for item in data:
        if not isinstance(item, tuple):
            continue
        match = _UID.search(item[0])
        if match is None:
            continue
        uid = match.group(1).decode()
        message_id = BytesHeaderParser().parsebytes(item[1]).get("Message-ID", "").strip()
        found.append((uid, message_id or f"uid:{uid}"))
    return found


class ImapMailbox:
    """Use as a context manager: the connection is closed on exit."""

    def __init__(self, config: ImapConfig) -> None:
        self.config = config
        self._imap: imaplib.IMAP4_SSL | None = None

    def __enter__(self) -> Self:
        imap = imaplib.IMAP4_SSL(
            self.config.host,
            self.config.port,
            ssl_context=ssl.create_default_context(),
            timeout=TIMEOUT_SECONDS,
        )
        try:
            imap.login(self.config.username, self.config.password)
            status, _ = imap.select(quote(self.config.folder), readonly=True)
            if status != "OK":
                raise imaplib.IMAP4.error("cannot open the folder")
        except BaseException:
            imap.logout()
            raise
        self._imap = imap
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._imap is not None:
            try:
                self._imap.logout()
            finally:
                self._imap = None

    @property
    def imap(self) -> imaplib.IMAP4_SSL:
        if self._imap is None:
            raise RuntimeError("mailbox not open")
        return self._imap

    def list_since(self, day: date) -> list[tuple[str, str]]:
        status, data = self.imap.uid("SEARCH", "SINCE", imap_date(day))
        if status != "OK" or not data or not data[0]:
            return []
        uids = b",".join(data[0].split()).decode()
        status, data = self.imap.uid("FETCH", uids, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
        return parse_header_fetch(data) if status == "OK" else []

    def fetch(self, uid: str) -> bytes:
        status, data = self.imap.uid("FETCH", uid, "(BODY.PEEK[])")
        for item in data if status == "OK" else []:
            if isinstance(item, tuple):
                return item[1]
        raise imaplib.IMAP4.error("message not found")
