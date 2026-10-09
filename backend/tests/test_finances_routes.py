import logging
from datetime import UTC, datetime, timedelta

import pytest

from tests.test_auth import login

BASE = "/api/modules/finances"
TODAY = datetime.now(UTC).date()
SOURCE = "https://www.service-public.fr/particuliers/vosdroits/F2365"


@pytest.fixture
def auth_client(client):
    login(client)
    return client


def accounts_by_kind(client) -> dict:
    return {a["kind"]: a for a in client.get(f"{BASE}/overview").json()["accounts"]}


def add_rate(client, product="livret_a", rate_bp=170, checked_on=TODAY):
    body = {
        "product": product,
        "rate_bp": rate_bp,
        "valid_from": "2026-08-01",
        "source_url": SOURCE,
        "checked_on": checked_on.isoformat(),
    }
    return client.post(f"{BASE}/rates", json=body)


def test_routes_require_session(client):
    assert client.get(f"{BASE}/overview").status_code == 401
    assert client.post(f"{BASE}/balances", json={}).status_code == 401


def test_four_accounts_seeded(auth_client):
    overview = auth_client.get(f"{BASE}/overview").json()
    kinds = [a["kind"] for a in overview["accounts"]]
    assert kinds == ["livret_a", "livret_jeune", "courant", "pro"]
    assert overview["accounts"][0]["ceiling_cents"] == 2_295_000
    assert "pas un conseil" in overview["disclaimer"]


def test_balance_ceiling_and_interest(auth_client):
    livret_a = accounts_by_kind(auth_client)["livret_a"]
    assert add_rate(auth_client).status_code == 201
    body = {"account_id": livret_a["id"], "day": TODAY.isoformat(), "amount_cents": 1_000_000}
    assert auth_client.post(f"{BASE}/balances", json=body).status_code == 201

    livret_a = accounts_by_kind(auth_client)["livret_a"]
    assert livret_a["balance_cents"] == 1_000_000
    assert livret_a["ceiling"]["remaining_cents"] == 1_295_000
    assert livret_a["rate_bp"] == 170
    assert livret_a["estimated_interest_cents"] == 17_000


def test_same_day_balance_is_replaced(auth_client):
    account = accounts_by_kind(auth_client)["courant"]
    body = {"account_id": account["id"], "day": TODAY.isoformat(), "amount_cents": 100}
    auth_client.post(f"{BASE}/balances", json=body)
    auth_client.post(f"{BASE}/balances", json=body | {"amount_cents": -2500})
    history = auth_client.get(f"{BASE}/balances", params={"account_id": account["id"]}).json()
    assert [b["amount_cents"] for b in history] == [-2500]

    assert auth_client.delete(f"{BASE}/balances/{history[0]['id']}").status_code == 204
    assert auth_client.get(f"{BASE}/balances").json() == []
    assert auth_client.delete(f"{BASE}/balances/{history[0]['id']}").status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"day": (TODAY + timedelta(days=1)).isoformat()},  # future
        {"day": "1999-12-31"},
        {"amount_cents": 10**12},
        {"account_id": 999},
    ],
)
def test_balance_validation(auth_client, change):
    account = accounts_by_kind(auth_client)["livret_a"]
    body = {"account_id": account["id"], "day": TODAY.isoformat(), "amount_cents": 100} | change
    assert auth_client.post(f"{BASE}/balances", json=body).status_code in (404, 422)


def test_rate_validation(auth_client):
    body = {
        "product": "livret_a",
        "rate_bp": 170,
        "valid_from": "2026-08-01",
        "source_url": "http://example.com",  # https only
        "checked_on": TODAY.isoformat(),
    }
    assert auth_client.post(f"{BASE}/rates", json=body).status_code == 422
    body |= {"source_url": "javascript:alert(1)"}
    assert auth_client.post(f"{BASE}/rates", json=body).status_code == 422
    body |= {"source_url": SOURCE, "rate_bp": 5000}
    assert auth_client.post(f"{BASE}/rates", json=body).status_code == 422
    body |= {"rate_bp": 170, "product": "pel"}
    assert auth_client.post(f"{BASE}/rates", json=body).status_code == 422


def test_rate_flags(auth_client):
    add_rate(auth_client, "livret_a", 170, checked_on=datetime(2026, 1, 15).date())
    add_rate(auth_client, "livret_jeune", 150)
    rates = {r["product"]: r for r in auth_client.get(f"{BASE}/overview").json()["rates"]}
    if datetime(2026, 2, 1).date() <= TODAY:
        assert rates["livret_a"]["needs_check"] is True  # checked before the last revision
    assert rates["livret_jeune"]["below_livret_a"] is True
    assert rates["livret_a"]["official_link"].startswith("https://")


def test_goals(auth_client):
    accounts = accounts_by_kind(auth_client)
    for kind, amount in (("livret_a", 300_000), ("livret_jeune", 100_000), ("courant", 50_000)):
        body = {
            "account_id": accounts[kind]["id"],
            "day": TODAY.isoformat(),
            "amount_cents": amount,
        }
        auth_client.post(f"{BASE}/balances", json=body)

    deadline = (TODAY + timedelta(days=365)).isoformat()
    auth_client.post(f"{BASE}/goals", json={"label": "Épargne", "target_cents": 1_000_000})
    auth_client.post(
        f"{BASE}/goals",
        json={
            "label": "Livret Jeune plein",
            "target_cents": 160_000,
            "deadline": deadline,
            "account_id": accounts["livret_jeune"]["id"],
        },
    )
    savings, jeune = auth_client.get(f"{BASE}/overview").json()["goals"]
    assert savings["current_cents"] == 400_000  # livrets only, not the current account
    assert savings["monthly_effort_cents"] is None
    assert jeune["remaining_cents"] == 60_000
    assert jeune["monthly_effort_cents"] == 5_000

    update = {"label": "Livret Jeune", "target_cents": 120_000, "account_id": None}
    assert auth_client.put(f"{BASE}/goals/{jeune['id']}", json=update).status_code == 204
    assert auth_client.delete(f"{BASE}/goals/{savings['id']}").status_code == 204
    (remaining,) = auth_client.get(f"{BASE}/overview").json()["goals"]
    assert remaining["label"] == "Livret Jeune"


def test_update_account(auth_client):
    account = accounts_by_kind(auth_client)["pro"]
    body = {"label": "Compte micro-entreprise", "ceiling_cents": None, "closes_on": None}
    assert auth_client.put(f"{BASE}/accounts/{account['id']}", json=body).status_code == 204
    assert accounts_by_kind(auth_client)["pro"]["label"] == "Compte micro-entreprise"


def test_deleting_account_balances_cascade(auth_client):
    """Foreign keys are enforced by SQLite (PRAGMA foreign_keys=ON)."""
    from modules.finances.models import Account, Balance

    account = accounts_by_kind(auth_client)["pro"]
    body = {"account_id": account["id"], "day": TODAY.isoformat(), "amount_cents": 1}
    auth_client.post(f"{BASE}/balances", json=body)
    with auth_client.app.state.session_factory() as db:
        db.delete(db.get(Account, account["id"]))
        db.commit()
        assert db.query(Balance).count() == 0


def test_text_plain_post_is_rejected(auth_client):
    """A cross-site HTML form can only send text/plain or form data: refuse it (CSRF)."""
    account = accounts_by_kind(auth_client)["livret_a"]
    payload = f'{{"account_id": {account["id"]}, "day": "{TODAY}", "amount_cents": 1}}'
    response = auth_client.post(
        f"{BASE}/balances", content=payload, headers={"Content-Type": "text/plain"}
    )
    assert response.status_code == 422


def test_amounts_never_logged(auth_client, caplog):
    account = accounts_by_kind(auth_client)["livret_a"]
    body = {"account_id": account["id"], "day": TODAY.isoformat(), "amount_cents": 1_234_567}
    with caplog.at_level(logging.DEBUG):
        auth_client.post(f"{BASE}/balances", json=body | {"note": "secret note"})
    assert "1234567" not in caplog.text
    assert "12345" not in caplog.text
    assert "secret note" not in caplog.text
