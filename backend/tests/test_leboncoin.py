"""Leboncoin module tests. No network: the IMAP server is faked. Data is fictitious."""

from datetime import date

import pytest
from pydantic import SecretStr

from modules.leboncoin import mailbox
from modules.leboncoin.mailbox import ImapConfig, ImapMailbox, imap_date, parse_header_fetch

IMAP_SETTINGS = {
    "lbc_imap_host": "imap.example.org",
    "lbc_imap_username": "alertes@example.org",
    "lbc_imap_password": SecretStr("app-password"),
}


class FakeImap:
    """Stands for imaplib.IMAP4_SSL and records every command."""

    instances: list["FakeImap"] = []

    def __init__(self, host, port, ssl_context=None, timeout=None):
        self.commands: list[tuple] = [("connect", host, port, ssl_context is not None)]
        FakeImap.instances.append(self)

    def login(self, user, password):
        self.commands.append(("login", user))
        return "OK", [b"logged in"]

    def select(self, folder, readonly=False):
        self.commands.append(("select", folder, readonly))
        return "OK", [b"2"]

    def uid(self, command, *args):
        self.commands.append(("uid", command, *args))
        if command == "SEARCH":
            return "OK", [b"41 42"]
        if args[1].startswith("(BODY.PEEK[HEADER"):
            return "OK", [
                (
                    b"1 (UID 41 BODY[HEADER.FIELDS (MESSAGE-ID)] {30}",
                    b"Message-ID: <a@lbc>\r\n\r\n",
                ),
                b")",
                (b"2 (UID 42 BODY[HEADER.FIELDS (MESSAGE-ID)] {2}", b"\r\n"),
                b")",
            ]
        return "OK", [(b"1 (UID 41 BODY[] {5}", b"hello"), b")"]

    def logout(self):
        self.commands.append(("logout",))


@pytest.fixture
def fake_imap(monkeypatch):
    FakeImap.instances = []
    monkeypatch.setattr(mailbox.imaplib, "IMAP4_SSL", FakeImap)
    return FakeImap


# --- Mailbox ----------------------------------------------------------------


def test_imap_config_requires_host_user_and_password(settings):
    assert ImapConfig.from_settings(settings) is None
    partial = settings.model_copy(update={"lbc_imap_host": "imap.example.org"})
    assert ImapConfig.from_settings(partial) is None
    config = ImapConfig.from_settings(settings.model_copy(update=IMAP_SETTINGS))
    assert config.password == "app-password"
    assert config.folder == "INBOX"


def test_imap_date_ignores_locale():
    assert imap_date(date(2026, 10, 1)) == "01-Oct-2026"


def test_parse_header_fetch_falls_back_to_uid():
    data = [(b"3 (UID 7 BODY[HEADER.FIELDS (MESSAGE-ID)] {2}", b"\r\n"), b")", b"junk"]
    assert parse_header_fetch(data) == [("7", "uid:7")]


def test_mailbox_is_read_only(settings, fake_imap):
    config = ImapConfig.from_settings(settings.model_copy(update=IMAP_SETTINGS))
    with ImapMailbox(config) as box:
        assert box.list_since(date(2026, 10, 1)) == [("41", "<a@lbc>"), ("42", "uid:42")]
        assert box.fetch("41") == b"hello"

    commands = fake_imap.instances[0].commands
    assert commands[0] == ("connect", "imap.example.org", 993, True)  # TLS context given
    assert ("select", '"INBOX"', True) in commands  # read-only
    fetches = [c for c in commands if c[:2] == ("uid", "FETCH")]
    assert all(c[3].startswith("(BODY.PEEK[") for c in fetches)  # never sets \Seen
    assert not any(c[0] == "uid" and c[1] in ("STORE", "COPY", "MOVE", "EXPUNGE") for c in commands)
    assert commands[-1] == ("logout",)
