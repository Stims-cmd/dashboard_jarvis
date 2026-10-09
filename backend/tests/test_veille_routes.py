from datetime import UTC, datetime, timedelta

import httpx2
import pytest

from app.core_models import LlmCall
from app.http import make_http_client
from modules.veille_cyber.collector import collect
from modules.veille_cyber.models import ProductSheet
from tests.test_auth import login
from tests.test_veille_collector import FakeLlm, fake_network, make_ctx

BASE = "/api/modules/veille_cyber"


@pytest.fixture
def db(client):
    with client.app.state.session_factory() as session:
        yield session


@pytest.fixture
def collected(client, db, settings, monkeypatch):
    """Run a collection for today against the recorded fixtures.

    A previous successful run is simulated, so every KEV entry counts as new
    whatever today's date is.
    """
    monkeypatch.setattr("modules.veille_cyber.sources.nvd.time.sleep", lambda seconds: None)
    now = datetime.now(UTC)
    with make_http_client(httpx2.MockTransport(fake_network)) as http:
        ctx = make_ctx(db, http, settings, FakeLlm(), now=now, last_success_at=now - timedelta(1))
        collect(ctx)


def test_routes_require_session(client):
    for path in ("/status", "/digest/latest", "/vulnerabilities", "/sheets"):
        assert client.get(BASE + path).status_code == 401


def test_empty_state(client):
    login(client)
    status = client.get(f"{BASE}/status").json()
    assert status["last_run"] is None
    assert status["llm_enabled"] is False
    assert status["llm_cost_month_usd"] == 0
    assert client.get(f"{BASE}/digest/latest").json() is None
    assert client.get(f"{BASE}/vulnerabilities").json() == []


def test_digest_sorted_by_priority(client, collected):
    login(client)
    digest = client.get(f"{BASE}/digest/latest").json()
    assert digest["text"] == "texte 1"
    vulns = digest["vulnerabilities"]
    assert len(vulns) == 7
    # Exploited (KEV) vulnerabilities come first.
    assert [v["in_kev"] for v in vulns] == sorted((v["in_kev"] for v in vulns), reverse=True)
    assert client.get(f"{BASE}/vulnerabilities", params={"days": 7}).json() == vulns


def test_sheets_and_cost(client, db, collected):
    db.add(
        LlmCall(
            created_at=datetime.now(UTC),
            purpose="test",
            model="claude-haiku-5-5",
            input_tokens=1000,
            output_tokens=1000,
            stop_reason="end_turn",
            cost_usd=0.0006,
        )
    )
    db.commit()
    login(client)
    assert client.get(f"{BASE}/status").json()["llm_cost_month_usd"] == 0.0006
    sheets = client.get(f"{BASE}/sheets").json()
    assert len(sheets) == db.query(ProductSheet).count()


def test_days_parameter_is_validated(client):
    login(client)
    assert client.get(f"{BASE}/vulnerabilities", params={"days": 0}).status_code == 422
    assert client.get(f"{BASE}/vulnerabilities", params={"days": 1000}).status_code == 422
