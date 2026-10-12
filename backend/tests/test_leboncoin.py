"""Leboncoin module tests. No network: the IMAP server is faked. Data is fictitious."""

import logging
from contextlib import contextmanager
from datetime import UTC, date, datetime
from email import message_from_bytes, policy
from email.message import EmailMessage

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.collect import CollectContext
from app.db import make_engine, make_session_factory, run_migrations
from app.http import make_http_client
from app.llm import LlmClient
from modules.leboncoin import mailbox, parser
from modules.leboncoin.collector import collect
from modules.leboncoin.mailbox import ImapConfig, ImapMailbox, imap_date, parse_header_fetch
from modules.leboncoin.models import Ad, Message
from modules.leboncoin.parser import AdData, Alert, is_authentic, parse_alert
from tests.test_auth import login

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
IMAP_SETTINGS = {
    "lbc_imap_host": "imap.example.org",
    "lbc_imap_username": "alertes@example.org",
    "lbc_imap_password": SecretStr("app-password"),
}
TRUSTED_RESULTS = "mx.example.org; dkim=pass header.i=@leboncoin.fr header.d=leboncoin.fr"


def alert_email(
    subject="Vélos à Lyon",
    sender="Leboncoin <alertes@leboncoin.fr>",
    results=(TRUSTED_RESULTS,),
    date_header="Mon, 12 Oct 2026 08:30:00 +0200",
) -> bytes:
    message = EmailMessage()
    for value in results:  # the first one is the topmost header
        message["Authentication-Results"] = value
    message["From"] = sender
    message["To"] = "alertes@example.org"
    message["Subject"] = subject
    message["Date"] = date_header
    message.set_content("text version")
    message.add_alternative("<html><body>ads</body></html>", subtype="html")
    return bytes(message)


def ad(ad_id="2849000001", price=15000, title="Vélo de ville") -> AdData:
    return AdData(
        ad_id=ad_id,
        title=title,
        price_cents=price,
        location="Lyon 69003",
        url=f"https://www.leboncoin.fr/ad/velos/{ad_id}",
    )


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


class FakeMailbox:
    """Stands for an open ImapMailbox. The uid is the index in the list."""

    def __init__(self, messages: list[bytes]):
        self.messages = messages
        self.fetched: list[str] = []

    def list_since(self, day):
        return [(str(i), f"<{i}@lbc>") for i in range(len(self.messages))]

    def fetch(self, uid):
        self.fetched.append(uid)
        return self.messages[int(uid)]


def with_ads(ads_by_subject: dict[str, list[AdData]]):
    """parse_alert whose ads depend on the subject.

    extract_ads waits for real alert samples; the authenticity check stays the real one.
    """

    def parse(raw: bytes) -> Alert | None:
        alert = parse_alert_with(raw, lambda html: [])
        if alert is None:
            return None
        if alert.search_name == "broken":
            raise ValueError("unexpected layout")
        return Alert(alert.search_name, alert.received_at, ads_by_subject[alert.search_name])

    return parse


def parse_alert_with(raw: bytes, extract) -> Alert | None:
    original = parser.extract_ads
    parser.extract_ads = extract
    try:
        return parse_alert(raw)
    finally:
        parser.extract_ads = original


@pytest.fixture
def fake_imap(monkeypatch):
    FakeImap.instances = []
    monkeypatch.setattr(mailbox.imaplib, "IMAP4_SSL", FakeImap)
    return FakeImap


@pytest.fixture
def lbc_settings(settings):
    return settings.model_copy(update=IMAP_SETTINGS)


@pytest.fixture
def db(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'lbc.db'}")
    run_migrations(engine)
    with make_session_factory(engine)() as session:
        yield session


def run(db, settings, box, monkeypatch, ads_by_subject, now=NOW):
    monkeypatch.setattr("modules.leboncoin.collector.parse_alert", with_ads(ads_by_subject))

    @contextmanager
    def open_mailbox(config):
        yield box

    with make_http_client() as http:
        ctx = CollectContext(db, http, LlmClient(settings, db), settings, now, None)
        return collect(ctx, open_mailbox=open_mailbox)


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


# --- Authenticity -----------------------------------------------------------


def test_authentic_alert_is_accepted():
    alert = parse_alert_with(alert_email(), lambda html: [ad()])
    assert alert.search_name == "Vélos à Lyon"
    assert alert.received_at == datetime(2026, 10, 12, 6, 30, tzinfo=UTC)
    assert alert.ads == [ad()]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"results": ()},  # no verification at all
        {"results": ("mx.example.org; dkim=fail header.d=leboncoin.fr",)},
        {"results": ("mx.example.org; dkim=pass header.d=leboncoin.fr.evil.com",)},
        {"results": ("mx.example.org; dkim=pass header.d=evil.com",)},
        {"sender": "Leboncoin <alertes@evil.com>"},
        # A forged header written by the sender sits below the one of our provider.
        {"results": ("mx.example.org; dkim=none", TRUSTED_RESULTS)},
    ],
)
def test_fake_alerts_are_refused(kwargs):
    raw = alert_email(**kwargs)
    assert not is_authentic(message_from_bytes(raw, policy=policy.default))
    assert parse_alert_with(raw, lambda html: [ad()]) is None


def test_subdomain_signature_is_accepted():
    raw = alert_email(
        results=("mx.example.org; dkim=pass header.d=mail.leboncoin.fr",),
        sender="alertes@mail.leboncoin.fr",
    )
    assert is_authentic(message_from_bytes(raw, policy=policy.default))


# --- Collector --------------------------------------------------------------


def test_collect_without_imap_skips(db, settings, monkeypatch):
    assert run(db, settings, FakeMailbox([]), monkeypatch, {}) == {"skipped": 1}


def test_collect_stores_ads_once(db, lbc_settings, monkeypatch):
    ads = {"Vélos à Lyon": [ad(), ad("2849000002", None, "Vélo enfant"), ad()]}
    box = FakeMailbox([alert_email()])
    counts = run(db, lbc_settings, box, monkeypatch, ads)
    assert counts == {"emails": 1, "new_ads": 2, "ignored": 0, "parse_errors": 0}

    stored = db.scalars(select(Ad).order_by(Ad.ad_id)).all()
    assert [a.ad_id for a in stored] == ["2849000001", "2849000002"]
    assert stored[0].search_name == "Vélos à Lyon"
    assert stored[1].price_cents is None
    assert [m.status for m in db.scalars(select(Message))] == ["ok"]

    # Second run: the email is already processed, it is not even downloaded again.
    box.fetched.clear()
    assert run(db, lbc_settings, box, monkeypatch, ads)["emails"] == 0
    assert box.fetched == []


def test_price_change_is_kept_in_history(db, lbc_settings, monkeypatch):
    first = alert_email(subject="a", date_header="Mon, 12 Oct 2026 08:00:00 +0000")
    second = alert_email(subject="b", date_header="Tue, 13 Oct 2026 10:00:00 +0200")
    ads = {"a": [ad(price=15000)], "b": [ad(price=12000)]}
    run(db, lbc_settings, FakeMailbox([first, second]), monkeypatch, ads)

    stored = db.scalar(select(Ad))
    assert stored.price_cents == 12000
    assert [price for _, price in stored.price_history] == [15000, 12000]
    assert stored.search_name == "a"  # first alert that listed it
    assert stored.last_seen_at == datetime(2026, 10, 13, 8, 0)  # stored as naive UTC


def test_bad_emails_do_not_stop_the_others(db, lbc_settings, monkeypatch):
    messages = [
        alert_email(subject="broken"),
        alert_email(subject="ok", sender="x@evil.com"),  # not authentic
        alert_email(subject="ok"),
    ]
    counts = run(db, lbc_settings, FakeMailbox(messages), monkeypatch, {"ok": [ad()]})
    assert counts == {"emails": 1, "new_ads": 1, "ignored": 1, "parse_errors": 1}

    # Only the parse error is tried again (the parser may have been fixed since).
    box = FakeMailbox(messages)
    run(db, lbc_settings, box, monkeypatch, {"ok": [ad()]})
    assert box.fetched == ["0"]


def test_nothing_personal_is_logged(db, lbc_settings, monkeypatch, caplog):
    messages = [alert_email(), alert_email(subject="broken")]
    with caplog.at_level(logging.DEBUG):
        run(db, lbc_settings, FakeMailbox(messages), monkeypatch, {"Vélos à Lyon": [ad()]})
    for secret in ("alertes@example.org", "app-password", "Vélo", "2849000001"):
        assert secret not in caplog.text


# --- Routes -----------------------------------------------------------------


def test_routes(client, settings, monkeypatch):
    assert client.get("/api/modules/leboncoin/ads").status_code == 401
    ads = {"a": [ad(), ad("2849000002")], "b": [ad("2849000003")]}
    messages = [alert_email(subject="a"), alert_email(subject="b")]
    with client.app.state.session_factory() as db:
        lbc_settings = settings.model_copy(update=IMAP_SETTINGS)
        run(db, lbc_settings, FakeMailbox(messages), monkeypatch, ads)
    login(client)

    listed = client.get("/api/modules/leboncoin/ads").json()
    assert len(listed) == 3
    assert listed[0]["first_seen_at"].endswith(("Z", "+00:00"))
    only_b = client.get("/api/modules/leboncoin/ads", params={"search": "b"}).json()
    assert [a["ad_id"] for a in only_b] == ["2849000003"]
    assert client.get("/api/modules/leboncoin/ads", params={"limit": 0}).status_code == 422
    searches = client.get("/api/modules/leboncoin/searches").json()
    assert searches == [{"name": "a", "ads": 2}, {"name": "b", "ads": 1}]
    status = client.get("/api/modules/leboncoin/status").json()
    assert status["total_ads"] == 3
    assert status["imap_configured"] is False  # the app's own settings have no mailbox
    assert status["stale"] is True  # run() called collect directly, without CollectorRun
