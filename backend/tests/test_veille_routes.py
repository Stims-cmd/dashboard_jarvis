from datetime import UTC, datetime

from app.core_models import LlmCall
from tests.test_auth import login

BASE = "/api/modules/veille_cyber"


def test_routes_require_session(client):
    for path in ("/status", "/digest/latest", "/articles"):
        assert client.get(BASE + path).status_code == 401


def test_empty_state(client):
    login(client)
    status = client.get(f"{BASE}/status").json()
    assert status["last_run"] is None
    assert status["stale"] is True
    assert status["llm_enabled"] is False
    assert status["llm_cost_month_usd"] == 0
    assert [s["status"] for s in status["sources"]] == [None] * 4
    assert client.get(f"{BASE}/digest/latest").json() is None
    assert client.get(f"{BASE}/articles").json() == []


def test_month_cost(client):
    with client.app.state.session_factory() as db:
        db.add(
            LlmCall(
                created_at=datetime.now(UTC),
                purpose="veille_cyber.digest",
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


def test_parameters_are_validated(client):
    login(client)
    assert client.get(f"{BASE}/articles", params={"days": 0}).status_code == 422
    assert client.get(f"{BASE}/articles", params={"days": 1000}).status_code == 422
    assert client.get(f"{BASE}/articles", params={"source": "x" * 51}).status_code == 422
