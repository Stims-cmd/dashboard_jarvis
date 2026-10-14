"""Veille cyber collector and routes. No network: recorded feeds served by a fake internet."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest
from sqlalchemy import func, select

from app.collect import CollectContext, run_collector
from app.core_models import CollectorRun
from app.db import make_engine, make_session_factory, run_migrations
from app.http import make_http_client
from app.llm import LlmClient
from modules.veille_cyber.collector import collect
from modules.veille_cyber.digest import digest_prompt
from modules.veille_cyber.models import Article, Digest
from tests.test_auth import login

FIXTURES = Path(__file__).parent / "fixtures" / "veille_cyber"
NOW = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)  # feeds were recorded on 2026-10-14
FILES = {
    "/alerte/feed/": "cert_fr_alerte.xml",
    "/cti/feed/": "cert_fr_cti.xml",
    "/actualite/feed/": "cert_fr_actualite.xml",
    "/feed/": "zataz.xml",
}


class FakeInternet:
    def __init__(self, broken: frozenset[str] = frozenset()):
        self.broken = broken
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if request.url.host in self.broken or request.url.path in self.broken:
            return httpx2.Response(503)
        name = FILES.get(request.url.path)
        if name is None:
            return httpx2.Response(404)
        return httpx2.Response(200, content=(FIXTURES / name).read_bytes())


class FakeLlm:
    enabled = True

    def __init__(self, answer="Revue du jour"):
        self.answer = answer
        self.calls: list[tuple[str, str, str]] = []

    def complete(self, purpose, system, prompt, max_tokens=8000):
        self.calls.append((purpose, system, prompt))
        return self.answer


@pytest.fixture
def db(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'veille.db'}")
    run_migrations(engine)
    with make_session_factory(engine)() as session:
        yield session


def run(db, settings, internet, llm=None, now=NOW, last_success_at=None):
    with make_http_client(httpx2.MockTransport(internet)) as http:
        llm = llm or LlmClient(settings, db)
        return collect(CollectContext(db, http, llm, settings, now, last_success_at))


def test_first_run_keeps_history_but_only_48h_are_new(db, settings):
    counts = run(db, settings, FakeInternet())
    # 12 articles stored; new = published since 2026-10-11 07:00 (Zataz x3, alert, bulletin).
    assert db.scalar(select(func.count(Article.id))) == 12
    assert counts == {"new_articles": 5, "feed_errors": 0, "digest": 0}
    digest = db.get(Digest, NOW.date())
    assert len(digest.article_ids) == 5
    assert set(digest.sources.values()) == {"ok"}
    assert digest.text is None  # no Claude key


def test_first_run_after_the_cve_version(db, settings):
    # The module already had successful runs (CVE era), but no article is stored yet.
    counts = run(db, settings, FakeInternet(), last_success_at=NOW - timedelta(hours=12))
    assert counts["new_articles"] == 5


def test_next_run_ignores_known_articles(db, settings):
    run(db, settings, FakeInternet())
    later = NOW + timedelta(hours=11)
    assert run(db, settings, FakeInternet(), now=later, last_success_at=NOW)["new_articles"] == 0
    assert db.scalar(select(func.count(Article.id))) == 12
    # Same day: the digest keeps the morning articles.
    assert len(db.get(Digest, NOW.date()).article_ids) == 5


def test_broken_feed_does_not_stop_the_others(db, settings):
    counts = run(db, settings, FakeInternet(broken=frozenset({"www.zataz.com"})))
    assert counts["feed_errors"] == 1
    assert counts["new_articles"] == 2
    assert db.get(Digest, NOW.date()).sources["zataz"] == "error"


def test_every_feed_broken_is_a_failed_run(db, settings):
    internet = FakeInternet(broken=frozenset({"cert.cyber.gouv.fr", "www.zataz.com"}))
    with make_http_client(httpx2.MockTransport(internet)) as http:
        run_ = run_collector("veille_cyber", db, settings, http, LlmClient(settings, db))
    assert run_.status == "error"
    assert db.scalar(select(func.count(CollectorRun.id))) == 1


def test_summary_with_claude(db, settings):
    llm = FakeLlm()
    counts = run(db, settings, FakeInternet(), llm=llm)
    assert counts["digest"] == 1
    assert db.get(Digest, NOW.date()).text == "Revue du jour"
    purpose, system, prompt = llm.calls[0]
    assert purpose == "veille_cyber.digest"
    assert "jamais une instruction" in system
    assert prompt.count("\n- [") == 5
    assert "<articles>" in prompt and "</articles>" in prompt
    assert "[Zataz, 2026-10-12] Une cyberattaque dérègle le froid des supermarchés" in prompt


def test_prompt_is_capped(db, settings):
    run(db, settings, FakeInternet())
    articles = list(db.scalars(select(Article)))
    prompt = digest_prompt(articles * 10)  # 120 items
    assert prompt.count("\n- [") == 60
    assert "60 autres articles non listés" in prompt


# --- Routes -----------------------------------------------------------------


def test_routes(client, settings):
    assert client.get("/api/modules/veille_cyber/digest/latest").status_code == 401
    with client.app.state.session_factory() as db:
        now = datetime.now(UTC)
        run(db, settings, FakeInternet(broken=frozenset({"www.zataz.com"})), now=now)
    login(client)

    digest = client.get("/api/modules/veille_cyber/digest/latest").json()
    assert digest["text"] is None
    dates = [a["published_at"] for a in digest["articles"]]
    assert dates == sorted(dates, reverse=True)

    articles = client.get("/api/modules/veille_cyber/articles").json()
    assert len(articles) == 9  # the 3 CERT-FR feeds
    only_cti = client.get("/api/modules/veille_cyber/articles", params={"source": "cert_fr_cti"})
    assert {a["source"] for a in only_cti.json()} == {"cert_fr_cti"}
    assert client.get("/api/modules/veille_cyber/articles", params={"days": 0}).status_code == 422

    status = client.get("/api/modules/veille_cyber/status").json()
    sources = {s["id"]: s["status"] for s in status["sources"]}
    assert sources == {
        "cert_fr_alerte": "ok",
        "cert_fr_cti": "ok",
        "cert_fr_actualite": "ok",
        "zataz": "error",
    }
    assert status["llm_enabled"] is False
