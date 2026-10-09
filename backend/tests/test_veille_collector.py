import json
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
from modules.veille_cyber import collector
from modules.veille_cyber.collector import collect
from modules.veille_cyber.models import Digest, ProductSheet, Vulnerability
from modules.veille_cyber.skills import is_known, load_skills

FIXTURES = Path(__file__).parent / "fixtures" / "veille_cyber"
NOW = datetime(2026, 10, 9, 4, 30, tzinfo=UTC)  # fixtures were recorded on 2026-10-09


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fake_network(request: httpx2.Request) -> httpx2.Response:
    """Answers like the real APIs, from the recorded fixtures."""
    url = str(request.url)
    if "known_exploited_vulnerabilities" in url:
        return httpx2.Response(200, json=fixture("kev.json"))
    if "services.nvd.nist.gov" in url:
        cve_id = request.url.params.get("cveId")
        if cve_id is None:
            return httpx2.Response(200, json=fixture("nvd_critical.json"))
        data = fixture("nvd_cve.json")
        if data["vulnerabilities"][0]["cve"]["id"] != cve_id:
            data = data | {"vulnerabilities": [], "resultsPerPage": 0, "totalResults": 0}
        return httpx2.Response(200, json=data)
    if "api.first.org" in url:
        return httpx2.Response(200, json=fixture("epss.json"))
    raise AssertionError(f"unexpected request: {url}")


class FakeLlm:
    enabled = True

    def __init__(self):
        self.calls = []

    def complete(self, purpose, system, prompt, max_tokens=8000):
        self.calls.append((purpose, system, prompt))
        return f"texte {len(self.calls)}"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("modules.veille_cyber.sources.nvd.time.sleep", lambda seconds: None)


@pytest.fixture
def db(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'veille.db'}")
    run_migrations(engine)
    with make_session_factory(engine)() as session:
        yield session


@pytest.fixture
def http():
    with make_http_client(httpx2.MockTransport(fake_network)) as client:
        yield client


def make_ctx(db, http, settings, llm, now=NOW, last_success_at=None):
    return CollectContext(db, http, llm, settings, now, last_success_at)


def test_first_run_without_claude(db, http, settings):
    counts = collect(make_ctx(db, http, settings, LlmClient(settings, db)))

    # Whole catalog stored, but only entries added in the last day count as new.
    assert db.scalar(select(func.count()).where(Vulnerability.in_kev)) == 4
    assert counts == {"new_kev": 3, "new_critical": 3, "digest": 0, "sheets": 0}

    bind = db.get(Vulnerability, "CVE-2015-5477")
    assert (bind.vendor, bind.product) == ("ISC", "BIND")  # KEV names kept over CPE names
    assert bind.description.startswith("named in ISC BIND")  # NVD description
    assert bind.epss is not None

    digest = db.get(Digest, NOW.date())
    assert len(digest.cve_ids) == 6
    assert "CVE-2021-44228" not in digest.cve_ids  # added to KEV in 2021
    assert digest.text is None


def test_second_run_creates_no_duplicates(db, http, settings):
    llm = LlmClient(settings, db)
    collect(make_ctx(db, http, settings, llm))
    later = NOW + timedelta(days=1)
    counts = collect(make_ctx(db, http, settings, llm, now=later, last_success_at=NOW))

    assert counts["new_kev"] == 0
    assert db.scalar(select(func.count()).select_from(Vulnerability)) == 7
    assert db.scalar(select(func.count()).select_from(Digest)) == 2


def test_digest_and_sheets_with_claude(db, http, settings, tmp_path):
    skills = tmp_path / "skills.md"
    skills.write_text("# Mes compétences\n- BIND\n- Apache Log4j2\n", encoding="utf-8")
    settings = settings.model_copy(update={"skills_file": skills})
    llm = FakeLlm()

    counts = collect(make_ctx(db, http, settings, llm))

    assert db.get(Digest, NOW.date()).text == "texte 1"
    purpose, _, prompt = llm.calls[0]
    assert purpose == "veille_cyber.digest"
    assert "CVE-2015-5477" in prompt
    # Sheets only for products absent from skills.md, never for BIND.
    sheet_products = set(db.scalars(select(ProductSheet.product)))
    assert counts["sheets"] == len(sheet_products) > 0
    assert "BIND" not in sheet_products
    # The skills list stays on the server.
    assert all("Mes compétences" not in call[2] for call in llm.calls)


def test_sheets_are_capped_and_not_regenerated(db, http, settings, tmp_path, monkeypatch):
    skills = tmp_path / "skills.md"
    skills.write_text("", encoding="utf-8")
    settings = settings.model_copy(update={"skills_file": skills})
    monkeypatch.setattr(collector, "MAX_SHEETS_PER_RUN", 1)

    assert collect(make_ctx(db, http, settings, FakeLlm()))["sheets"] == 1
    later = NOW + timedelta(hours=1)
    collect(make_ctx(db, http, settings, FakeLlm(), now=later, last_success_at=NOW))
    keys = list(db.scalars(select(ProductSheet.product_key)))
    assert len(keys) == len(set(keys)) == 2


def test_no_sheets_without_skills_file(db, http, settings, tmp_path):
    settings = settings.model_copy(update={"skills_file": tmp_path / "missing.md"})
    assert collect(make_ctx(db, http, settings, FakeLlm()))["sheets"] == 0


def test_run_collector_records_failure(db, settings):
    with make_http_client(httpx2.MockTransport(lambda r: httpx2.Response(503))) as http:
        run = run_collector("veille_cyber", db, settings, http, LlmClient(settings, db))
    assert run.status == "error"
    assert "HTTPStatusError" in run.summary
    assert db.scalar(select(func.count()).select_from(Vulnerability)) == 0


def test_run_collector_records_success(db, http, settings):
    run = run_collector("veille_cyber", db, settings, http, LlmClient(settings, db))
    assert run.status == "ok"
    assert "new_critical=" in run.summary
    assert db.scalars(select(CollectorRun)).one().finished_at is not None


def test_skills_matching(tmp_path):
    path = tmp_path / "skills.md"
    path.write_text("- Apache HTTP Server\n* nginx\nnot a list item\n", encoding="utf-8")
    skills = load_skills(path)
    assert skills == {"apache http server", "nginx"}
    assert is_known(skills, "Apache", "HTTP Server")
    assert is_known(skills, "F5", "NGINX")
    assert not is_known(skills, "Microsoft", "Exchange Server")
    assert load_skills(tmp_path / "absent.md") is None
