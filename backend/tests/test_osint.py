"""OSINT module tests. Every identifier here is fictitious."""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app.collect import CollectContext
from app.db import make_engine, make_session_factory, run_migrations
from app.http import make_http_client
from app.llm import LlmClient
from modules.osint.collector import collect, week_of
from modules.osint.config import load_targets, phone_variants
from modules.osint.models import Finding, Report
from modules.osint.sources.brave import parse_results
from modules.osint.sources.gravatar import email_hash
from modules.osint.sources.xon import parse_breaches
from tests.test_auth import login

FIXTURES = Path(__file__).parent / "fixtures" / "osint"
EMAIL = "camille.exemple@example.org"
PHONE = "+33 6 00 00 00 01"
NAME = "Camille Exemple"
NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)  # a Monday

TARGETS = f"""
names = ["{NAME}"]
usernames = ["camexemple"]

[[emails]]
label = "perso"
value = "{EMAIL}"

[[phones]]
label = "mobile"
value = "{PHONE}"
"""


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeInternet:
    """Answers like the real APIs. Records requests to check what leaves the server."""

    def __init__(self, broken: set[str] = frozenset()):
        self.broken = broken
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        host = request.url.host
        if host in self.broken:
            return httpx2.Response(503)
        if host == "api.xposedornot.com":
            return httpx2.Response(200, json=fixture("xon_analytics.json"))
        if host == "api.gravatar.com":
            return httpx2.Response(404, json={"error": "Profile not found"})
        if host == "api.search.brave.com":
            return httpx2.Response(200, json=fixture("brave_search.json"))
        if host == "api.github.com":
            return httpx2.Response(200, json={"login": "camexemple"})
        if host == "gitlab.com":
            return httpx2.Response(200, json=[])  # GitLab: empty list = no such user
        if host == "hacker-news.firebaseio.com":
            return httpx2.Response(200, content=b"null")  # HN: null = no such user
        if host == "keybase.io":
            return httpx2.Response(200, json={"them": [None]})
        return httpx2.Response(404)


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr("modules.osint.collector.time.sleep", lambda seconds: None)


@pytest.fixture
def targets_file(tmp_path):
    path = tmp_path / "osint.toml"
    path.write_text(TARGETS, encoding="utf-8")
    return path


@pytest.fixture
def osint_settings(settings, targets_file):
    return settings.model_copy(update={"osint_file": targets_file, "brave_api_key": None})


@pytest.fixture
def db(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'osint.db'}")
    run_migrations(engine)
    with make_session_factory(engine)() as session:
        yield session


def run(db, settings, internet, now=NOW):
    with make_http_client(httpx2.MockTransport(internet)) as http:
        ctx = CollectContext(db, http, LlmClient(settings, db), settings, now, None)
        return collect(ctx)


# --- Configuration ----------------------------------------------------------


def test_load_targets(targets_file, tmp_path):
    targets = load_targets(targets_file)
    assert targets.emails[0].label == "perso"
    assert targets.usernames == ["camexemple"]
    assert load_targets(tmp_path / "missing.toml") is None


@pytest.mark.parametrize(
    "content",
    ['usernames = ["../admin"]', 'usernames = ["a/b"]', "names = [", "[[emails]]\nlabel = 'x'"],
)
def test_invalid_targets_are_refused(tmp_path, content, caplog):
    path = tmp_path / "osint.toml"
    path.write_text(content, encoding="utf-8")
    assert load_targets(path) is None


def test_phone_variants():
    assert phone_variants("+33 6 00 00 00 01") == ["06 00 00 00 01", "+33600000001"]
    assert phone_variants("06.00.00.00.01") == ["06 00 00 00 01", "+33600000001"]


# --- Parsers ----------------------------------------------------------------


def test_parse_breaches():
    findings = parse_breaches(fixture("xon_analytics.json"), "e-mail perso")
    assert [f.key for f in findings] == ["McKesson", "ManchesterAirportsGroup", "Sharecare"]
    assert "Phone numbers" in findings[0].details["data"]
    assert parse_breaches(fixture("xon_not_found.json"), "e-mail perso") == []


def test_parse_brave_strips_html():
    findings = parse_results(fixture("brave_search.json"), "nom")
    assert findings[0].key == "https://example.org/profil/camille-exemple"
    assert "<strong>" not in findings[0].details["snippet"]


def test_gravatar_sends_only_a_hash():
    assert email_hash(" Camille.Exemple@Example.org ") == email_hash(EMAIL)
    assert len(email_hash(EMAIL)) == 64


# --- Collector --------------------------------------------------------------


def test_collect_without_brave_key(db, osint_settings):
    internet = FakeInternet()
    counts = run(db, osint_settings, internet)

    kinds = dict(db.execute(select(Finding.kind, func.count()).group_by(Finding.kind)).all())
    assert kinds == {"breach": 3, "account": 1}  # GitHub only; others answered "no such user"
    assert counts == {"findings": 4, "new": 4, "source_errors": 0}
    report = db.get(Report, week_of(NOW.date()))
    assert report.sources["brave"] == "disabled"
    assert len(report.new_finding_ids) == 4
    # The email never travels in clear to Gravatar; Brave was never called.
    assert all(
        EMAIL not in str(r.url) for r in internet.requests if r.url.host == "api.gravatar.com"
    )
    assert not any(r.url.host == "api.search.brave.com" for r in internet.requests)


def test_stored_subjects_are_labels_not_identifiers(db, osint_settings):
    run(db, osint_settings.model_copy(update={"brave_api_key": SecretStr("key")}), FakeInternet())
    subjects = set(db.scalars(select(Finding.subject)))
    assert subjects == {"e-mail perso", "camexemple", "nom", "téléphone mobile"}


def test_second_run_reports_only_new_findings(db, osint_settings):
    run(db, osint_settings, FakeInternet())
    next_week = NOW + timedelta(days=7)
    counts = run(db, osint_settings, FakeInternet(), now=next_week)

    assert counts["new"] == 0
    assert db.scalar(select(func.count()).select_from(Finding)) == 4
    assert db.get(Report, week_of(next_week.date())).new_finding_ids == []
    assert all(f.last_seen_at.date() == next_week.date() for f in db.scalars(select(Finding)))


def test_failing_source_does_not_stop_others(db, osint_settings):
    counts = run(db, osint_settings, FakeInternet(broken={"api.xposedornot.com"}))
    report = db.get(Report, week_of(NOW.date()))
    assert report.sources["xposedornot"] == "error"
    assert report.sources["platforms"] == "ok"
    assert counts["source_errors"] == 1
    assert db.scalar(select(func.count()).where(Finding.kind == "account")) == 1


def test_brave_queries_name_and_phone_variants(db, osint_settings):
    internet = FakeInternet()
    run(db, osint_settings.model_copy(update={"brave_api_key": SecretStr("key")}), internet)
    queries = [r.url.params["q"] for r in internet.requests if r.url.host == "api.search.brave.com"]
    assert queries == [f'"{NAME}"', '"06 00 00 00 01"', '"+33600000001"']
    assert all(
        r.headers["X-Subscription-Token"] == "key"
        for r in internet.requests
        if r.url.host == "api.search.brave.com"
    )


def test_missing_targets_file_skips(db, settings, tmp_path):
    settings = settings.model_copy(update={"osint_file": tmp_path / "absent.toml"})
    assert run(db, settings, FakeInternet()) == {"skipped": 1}


def test_identifiers_never_logged(db, osint_settings, caplog):
    """Including httpx2's own request logs and failing sources' error messages."""
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # as set by app.collect.main()
    with caplog.at_level(logging.DEBUG):
        run(
            db,
            osint_settings.model_copy(update={"brave_api_key": SecretStr("key")}),
            FakeInternet(broken={"api.xposedornot.com"}),
        )
    for secret in (EMAIL, "camille.exemple", "600000001", "00 00 00 01", NAME):
        assert secret not in caplog.text


# --- Routes -----------------------------------------------------------------


def test_routes(client, osint_settings):
    assert client.get("/api/modules/osint/report/latest").status_code == 401
    with client.app.state.session_factory() as db:
        run(db, osint_settings, FakeInternet())
    login(client)

    report = client.get("/api/modules/osint/report/latest").json()
    assert len(report["new_findings"]) == 4
    assert report["sources"]["brave"] == "disabled"
    breaches = client.get("/api/modules/osint/findings", params={"kind": "breach"}).json()
    assert len(breaches) == 3
    assert client.get("/api/modules/osint/findings", params={"kind": "x"}).status_code == 422
    status = client.get("/api/modules/osint/status").json()
    assert status["total_findings"] == 4
