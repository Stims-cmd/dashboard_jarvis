"""Sale assistant tests (Leboncoin module). No network. Data is fictitious."""

from datetime import UTC, date, datetime, timedelta

import pytest

from modules.leboncoin.sales import (
    comparables_stats,
    euros,
    price_reminder,
    redact,
    suggested_price_cents,
    template_draft,
)
from tests.test_auth import login

BASE = "/api/modules/leboncoin/items"
TODAY = date(2026, 10, 12)
BIKE = {
    "title": "Vélo de ville 28 pouces",
    "condition": "bon",
    "notes": "Quelques rayures sur le cadre. Antivol fourni.",
    "keywords": "vélo ville",
    "asking_price_cents": 15000,
    "floor_price_cents": 11000,
}


def reminder(**overrides):
    args = {
        "status": "listed",
        "listed_on": TODAY - timedelta(days=20),
        "asking_cents": 15000,
        "floor_cents": 11000,
        "lower_after_days": 14,
        "price_history": [[(TODAY - timedelta(days=20)).isoformat(), 15000]],
        "today": TODAY,
    } | overrides
    return price_reminder(**args)


# --- Pure helpers -----------------------------------------------------------


def test_reminder_due_after_delay():
    result = reminder()
    assert result.due
    assert result.suggested_cents == 13500
    assert not result.at_floor


def test_reminder_not_due_before_delay():
    assert not reminder(listed_on=TODAY - timedelta(days=13), price_history=[]).due


def test_reminder_restarts_after_price_drop():
    result = reminder(price_history=[["2026-09-01", 18000], [TODAY.isoformat(), 15000]])
    assert result.since == TODAY
    assert not result.due


def test_initial_price_does_not_restart_the_delay():
    # Item added today, but already listed on Leboncoin for 20 days.
    assert reminder(price_history=[[TODAY.isoformat(), 15000]]).due


def test_reminder_only_for_listed_items():
    assert reminder(status="draft") is None
    assert reminder(status="sold") is None
    assert reminder(listed_on=None) is None


def test_suggestion_respects_floor():
    assert suggested_price_cents(12000, 11500) == 11500
    assert suggested_price_cents(11000, 11000) is None
    assert suggested_price_cents(1999, None) == 1700  # rounded down to the euro
    assert reminder(asking_cents=11000).at_floor


def test_comparables_stats():
    stats = comparables_stats([10000, 30000, 12000, 20000])
    assert (stats.count, stats.min_cents, stats.median_cents, stats.max_cents) == (
        4,
        10000,
        16000,
        30000,
    )
    assert comparables_stats([]).median_cents is None


@pytest.mark.parametrize(
    "secret",
    [
        "camille.exemple@example.org",
        "06 00 00 00 01",
        "06.00.00.00.01",
        "0600000001",
        "+33 6 00 00 00 01",
        "+33600000001",
        "FR76 3000 6000 0112 3456 7890 189",
    ],
)
def test_redact_removes_contact_details(secret):
    text = redact(f"Contact : {secret} après 18h. Vélo 28 pouces, 2019.")
    assert secret not in text
    assert "[retiré]" in text
    assert "28 pouces, 2019" in text  # ordinary numbers stay


def test_template_draft():
    title, body = template_draft("Vélo", "tres_bon", "Antivol fourni.", 125050)
    assert title == "Vélo"
    assert "très bon état" in body
    assert "Antivol fourni." in body
    assert "1 250,50 €" in body
    assert euros(15000) == "150 €"


# --- Routes -----------------------------------------------------------------


def test_items_require_login(client):
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json=BIKE).status_code == 401


def test_item_lifecycle(client):
    login(client)
    created = client.post(BASE, json=BIKE)
    assert created.status_code == 201
    item = created.json()
    assert item["price_history"][0][1] == 15000
    assert item["reminder"] is None  # not listed yet

    listed_on = (datetime.now(UTC).date() - timedelta(days=30)).isoformat()
    updated = client.put(
        f"{BASE}/{item['id']}", json=BIKE | {"status": "listed", "listed_on": listed_on}
    ).json()
    assert updated["reminder"]["due"] is True
    assert updated["reminder"]["suggested_cents"] == 13500

    # Lowering the price adds to the history and restarts the delay.
    lowered = client.put(
        f"{BASE}/{item['id']}",
        json=BIKE | {"status": "listed", "listed_on": listed_on, "asking_price_cents": 13500},
    ).json()
    assert [price for _, price in lowered["price_history"]] == [15000, 13500]
    assert lowered["reminder"]["due"] is False

    assert len(client.get(BASE).json()) == 1
    assert client.delete(f"{BASE}/{item['id']}").status_code == 204
    assert client.get(BASE).json() == []
    assert client.delete(f"{BASE}/{item['id']}").status_code == 404


def test_listing_date_defaults_to_today(client):
    login(client)
    item = client.post(BASE, json=BIKE | {"status": "listed"}).json()
    assert item["listed_on"] == datetime.now(UTC).date().isoformat()


@pytest.mark.parametrize(
    "change",
    [
        {"floor_price_cents": 20000},  # above the asking price
        {"asking_price_cents": -1},
        {"condition": "excellent"},
        {"title": ""},
        {"notes": "x" * 2001},
        {"listed_on": (date.today() + timedelta(days=2)).isoformat()},
    ],
)
def test_invalid_items_are_refused(client, change):
    login(client)
    assert client.post(BASE, json=BIKE | change).status_code == 422


# --- Comparables ------------------------------------------------------------


def add_ads(client, ads: list[tuple[str, int | None]]):
    from modules.leboncoin.models import Ad

    now = datetime.now(UTC)
    with client.app.state.session_factory() as db:
        for number, (title, price) in enumerate(ads):
            db.add(
                Ad(
                    ad_id=str(2849000000 + number),
                    search_name="vélos",
                    title=title,
                    price_cents=price,
                    location="Lyon",
                    url=f"https://www.leboncoin.fr/ad/velos/{2849000000 + number}",
                    price_history=[],
                    first_seen_at=now - timedelta(minutes=number),
                    last_seen_at=now,
                )
            )
        db.commit()


def test_comparables(client):
    add_ads(
        client,
        [
            ("Vélo de VILLE femme", 12000),
            ("vélo ville Peugeot", 18000),
            ("Vélo ville", None),  # no price: listed, but not in the stats
            ("Vélo de course", 40000),  # missing "ville"
            ("Trottinette ville", 9000),
        ],
    )
    login(client)
    item = client.post(BASE, json=BIKE).json()
    result = client.get(f"{BASE}/{item['id']}/comparables").json()
    assert result["keywords"] == ["vélo", "ville"]
    assert len(result["ads"]) == 3
    assert (result["count"], result["min_cents"], result["median_cents"]) == (2, 12000, 15000)


def test_comparables_keywords_are_literal(client):
    add_ads(client, [("Vélo 100 ans", 5000), ("Vélo 100% neuf", 8000)])
    login(client)
    item = client.post(BASE, json=BIKE | {"keywords": "100%"}).json()
    result = client.get(f"{BASE}/{item['id']}/comparables").json()
    assert [a["title"] for a in result["ads"]] == ["Vélo 100% neuf"]


def test_comparables_without_keywords(client):
    login(client)
    item = client.post(BASE, json=BIKE | {"keywords": " "}).json()
    assert client.get(f"{BASE}/{item['id']}/comparables").json()["count"] == 0
    assert client.get(f"{BASE}/999/comparables").status_code == 404
