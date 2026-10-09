from datetime import date

import pytest

from modules.finances.service import (
    ceiling_status,
    estimated_yearly_interest_cents,
    goal_progress,
    last_revision_date,
    months_between,
    rate_needs_check,
)


def test_ceiling_status():
    status = ceiling_status(balance_cents=2_000_000, ceiling_cents=2_295_000)
    assert status.remaining_cents == 295_000
    assert status.near_ceiling is False
    assert ceiling_status(2_100_000, 2_295_000).near_ceiling is True
    # Capitalized interest can push a Livret A above its ceiling.
    assert ceiling_status(2_400_000, 2_295_000).remaining_cents == 0


def test_estimated_interest():
    assert estimated_yearly_interest_cents(1_000_000, 150) == 15_000  # 10 000 € at 1.50 %
    assert estimated_yearly_interest_cents(0, 300) == 0


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 1, 31), date(2025, 8, 1)),
        (date(2026, 2, 1), date(2026, 2, 1)),
        (date(2026, 7, 31), date(2026, 2, 1)),
        (date(2026, 10, 9), date(2026, 8, 1)),
    ],
)
def test_last_revision_date(today, expected):
    assert last_revision_date(today) == expected


def test_rate_needs_check():
    today = date(2026, 10, 9)
    assert rate_needs_check(None, today)
    assert rate_needs_check(date(2026, 7, 31), today)  # checked before the 1 August revision
    assert not rate_needs_check(date(2026, 8, 1), today)


def test_months_between():
    assert months_between(date(2026, 10, 9), date(2027, 10, 9)) == 12
    assert months_between(date(2026, 10, 9), date(2026, 10, 20)) == 1
    assert months_between(date(2026, 10, 9), date(2026, 10, 1)) == 0


def test_goal_with_deadline():
    progress = goal_progress(50_000, 170_000, date(2027, 10, 9), today=date(2026, 10, 9))
    assert progress.remaining_cents == 120_000
    assert progress.ratio == pytest.approx(50_000 / 170_000)
    assert progress.monthly_effort_cents == 10_000  # 1 200 € over 12 months


def test_goal_without_deadline_or_reached():
    assert goal_progress(10, 100, None, date(2026, 1, 1)).monthly_effort_cents is None
    reached = goal_progress(200, 100, date(2027, 1, 1), date(2026, 1, 1))
    assert (reached.ratio, reached.remaining_cents, reached.monthly_effort_cents) == (1.0, 0, None)


def test_goal_past_deadline_asks_everything_now():
    progress = goal_progress(0, 1000, date(2026, 1, 1), today=date(2026, 6, 1))
    assert progress.months_left == 0
    assert progress.monthly_effort_cents == 1000
