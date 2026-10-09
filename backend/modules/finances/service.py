"""Pure calculations of the Finances module (no database, easy to test).

Indicative information only, not financial advice. Real interest on regulated
savings accounts is computed by fortnights (quinzaines): the yearly figure here
is an estimate.
"""

import math
from dataclasses import dataclass
from datetime import date

NEAR_CEILING_RATIO = 0.9
# Regulated savings rates (Livret A) are revised on 1 February and 1 August.
REVISION_DAYS = ((2, 1), (8, 1))


@dataclass(frozen=True)
class CeilingStatus:
    remaining_cents: int
    used_ratio: float
    near_ceiling: bool


def ceiling_status(balance_cents: int, ceiling_cents: int) -> CeilingStatus:
    ratio = balance_cents / ceiling_cents if ceiling_cents > 0 else 0.0
    return CeilingStatus(
        remaining_cents=max(ceiling_cents - balance_cents, 0),
        used_ratio=ratio,
        near_ceiling=ratio >= NEAR_CEILING_RATIO,
    )


def estimated_yearly_interest_cents(balance_cents: int, rate_bp: int) -> int:
    """Balance x rate over 12 months (rate in basis points: 150 = 1.50 %)."""
    return round(balance_cents * rate_bp / 10_000)


def last_revision_date(today: date) -> date:
    """Most recent 1 February or 1 August on or before today."""
    candidates = [
        date(year, month, day)
        for year in (today.year - 1, today.year)
        for month, day in REVISION_DAYS
    ]
    return max(d for d in candidates if d <= today)


def rate_needs_check(checked_on: date | None, today: date) -> bool:
    """True if the rate was not checked since the last official revision date."""
    return checked_on is None or checked_on < last_revision_date(today)


@dataclass(frozen=True)
class GoalProgress:
    current_cents: int
    remaining_cents: int
    ratio: float
    months_left: int | None
    monthly_effort_cents: int | None  # needed per month to reach the goal on time


def months_between(start: date, end: date) -> int:
    """Whole months from start to end, at least 1 when end is in the future."""
    months = (end.year - start.year) * 12 + end.month - start.month
    if end.day < start.day:
        months -= 1
    return max(months, 1) if end > start else 0


def goal_progress(
    current_cents: int, target_cents: int, deadline: date | None, today: date
) -> GoalProgress:
    remaining = max(target_cents - current_cents, 0)
    months_left = months_between(today, deadline) if deadline else None
    effort = None
    if months_left is not None and remaining > 0:
        effort = math.ceil(remaining / months_left) if months_left else remaining
    return GoalProgress(
        current_cents=current_cents,
        remaining_cents=remaining,
        ratio=min(current_cents / target_cents, 1.0) if target_cents > 0 else 1.0,
        months_left=months_left,
        monthly_effort_cents=effort,
    )
