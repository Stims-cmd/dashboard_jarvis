"""API of the Finances window (mounted under /api/modules/finances).

Logs record actions only, never amounts or labels.
"""

import logging
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from app.deps import DbSession
from modules.finances import service
from modules.finances.models import Account, Balance, Goal, Rate

logger = logging.getLogger(__name__)
router = APIRouter()

SOURCE_LINKS = {
    "livret_a": "https://www.service-public.fr/particuliers/vosdroits/F2365",
    "livret_jeune": (
        "https://www.economie.gouv.fr/particuliers/gerer-mon-argent/"
        "gerer-mon-budget-et-mon-epargne/livret-jeune-quelles-sont-ses-caracteristiques"
    ),
}
DISCLAIMER = (
    "Information indicative, pas un conseil en investissement. "
    "Taux et règles fiscales à vérifier à la source (service-public.fr, economie.gouv.fr)."
)
MAX_CENTS = 1_000_000_000  # 10 M€
RATE_PRODUCT_OF_KIND = {"livret_a": "livret_a", "livret_jeune": "livret_jeune"}
SAVINGS_KINDS = ("livret_a", "livret_jeune")


def _not_in_future(value: date) -> date:
    if value > datetime.now(UTC).date():
        raise ValueError("date in the future")
    return value


# --- Input models ---------------------------------------------------------


class BalanceIn(BaseModel):
    account_id: int
    day: date = Field(ge=date(2000, 1, 1))
    amount_cents: int = Field(ge=-MAX_CENTS, le=MAX_CENTS)  # a current account can be negative
    note: str | None = Field(default=None, max_length=200)

    _check_day = field_validator("day")(_not_in_future)


class AccountIn(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    ceiling_cents: int | None = Field(default=None, ge=0, le=MAX_CENTS)
    closes_on: date | None = None


class RateIn(BaseModel):
    product: Literal["livret_a", "livret_jeune"]
    rate_bp: int = Field(ge=0, le=2000)  # 0 to 20 %
    valid_from: date = Field(ge=date(2000, 1, 1))
    source_url: str = Field(max_length=500, pattern=r"^https://\S+$")
    checked_on: date = Field(ge=date(2000, 1, 1))

    _check_checked_on = field_validator("checked_on")(_not_in_future)


class GoalIn(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    target_cents: int = Field(gt=0, le=MAX_CENTS)
    deadline: date | None = None
    account_id: int | None = None


# --- Output models --------------------------------------------------------


class CeilingOut(BaseModel):
    remaining_cents: int
    used_ratio: float
    near_ceiling: bool


class AccountOut(BaseModel):
    id: int
    label: str
    kind: str
    ceiling_cents: int | None
    closes_on: date | None
    balance_cents: int | None
    balance_day: date | None
    ceiling: CeilingOut | None
    rate_bp: int | None
    estimated_interest_cents: int | None


class RateOut(BaseModel):
    product: str
    rate_bp: int | None
    valid_from: date | None
    source_url: str | None
    checked_on: date | None
    needs_check: bool
    below_livret_a: bool
    official_link: str


class GoalOut(BaseModel):
    id: int
    label: str
    target_cents: int
    deadline: date | None
    account_id: int | None
    current_cents: int
    remaining_cents: int
    ratio: float
    monthly_effort_cents: int | None


class OverviewOut(BaseModel):
    today: date
    accounts: list[AccountOut]
    rates: list[RateOut]
    goals: list[GoalOut]
    disclaimer: str


class BalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    day: date
    amount_cents: int
    note: str | None


# --- Helpers --------------------------------------------------------------


def _today() -> date:
    return datetime.now(UTC).date()


def _current_rates(db: DbSession, today: date) -> dict[str, Rate]:
    """Latest rate already in force for each product."""
    rates: dict[str, Rate] = {}
    query = (
        select(Rate)
        .where(Rate.valid_from <= today)
        .order_by(Rate.valid_from, Rate.checked_on, Rate.id)
    )
    for rate in db.scalars(query):
        rates[rate.product] = rate  # later rows win
    return rates


def _latest_balances(db: DbSession) -> dict[int, Balance]:
    latest: dict[int, Balance] = {}
    for balance in db.scalars(select(Balance).order_by(Balance.day, Balance.id)):
        latest[balance.account_id] = balance
    return latest


def _get_or_404(db: DbSession, model, item_id: int):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return item


# --- Routes ---------------------------------------------------------------


@router.get("/overview")
def overview(db: DbSession) -> OverviewOut:
    today = _today()
    rates = _current_rates(db, today)
    balances = _latest_balances(db)
    accounts = list(db.scalars(select(Account).order_by(Account.position, Account.id)))

    account_out = []
    for account in accounts:
        balance = balances.get(account.id)
        rate = rates.get(RATE_PRODUCT_OF_KIND.get(account.kind, ""))
        ceiling = None
        if balance and account.ceiling_cents:
            ceiling = CeilingOut(
                **vars(service.ceiling_status(balance.amount_cents, account.ceiling_cents))
            )
        account_out.append(
            AccountOut(
                id=account.id,
                label=account.label,
                kind=account.kind,
                ceiling_cents=account.ceiling_cents,
                closes_on=account.closes_on,
                balance_cents=balance.amount_cents if balance else None,
                balance_day=balance.day if balance else None,
                ceiling=ceiling,
                rate_bp=rate.rate_bp if rate else None,
                estimated_interest_cents=(
                    service.estimated_yearly_interest_cents(
                        max(balance.amount_cents, 0), rate.rate_bp
                    )
                    if balance and rate
                    else None
                ),
            )
        )

    livret_a = rates.get("livret_a")
    rate_out = []
    for product, link in SOURCE_LINKS.items():
        rate = rates.get(product)
        rate_out.append(
            RateOut(
                product=product,
                rate_bp=rate.rate_bp if rate else None,
                valid_from=rate.valid_from if rate else None,
                source_url=rate.source_url if rate else None,
                checked_on=rate.checked_on if rate else None,
                needs_check=service.rate_needs_check(rate.checked_on if rate else None, today),
                # The Livret Jeune rate can never be below the Livret A rate.
                below_livret_a=bool(
                    product == "livret_jeune"
                    and rate
                    and livret_a
                    and rate.rate_bp < livret_a.rate_bp
                ),
                official_link=link,
            )
        )

    savings_total = sum(
        balances[a.id].amount_cents
        for a in accounts
        if a.kind in SAVINGS_KINDS and a.id in balances
    )
    goal_out = []
    for goal in db.scalars(select(Goal).order_by(Goal.created_at, Goal.id)):
        if goal.account_id is None:
            current = savings_total
        else:
            balance = balances.get(goal.account_id)
            current = balance.amount_cents if balance else 0
        progress = service.goal_progress(max(current, 0), goal.target_cents, goal.deadline, today)
        goal_out.append(
            GoalOut(
                id=goal.id,
                label=goal.label,
                target_cents=goal.target_cents,
                deadline=goal.deadline,
                account_id=goal.account_id,
                current_cents=progress.current_cents,
                remaining_cents=progress.remaining_cents,
                ratio=progress.ratio,
                monthly_effort_cents=progress.monthly_effort_cents,
            )
        )

    return OverviewOut(
        today=today, accounts=account_out, rates=rate_out, goals=goal_out, disclaimer=DISCLAIMER
    )


@router.get("/balances")
def list_balances(db: DbSession, account_id: int | None = Query(default=None)) -> list[BalanceOut]:
    query = select(Balance).order_by(Balance.day.desc(), Balance.id.desc()).limit(200)
    if account_id is not None:
        query = query.where(Balance.account_id == account_id)
    return list(db.scalars(query))


@router.post("/balances", status_code=status.HTTP_201_CREATED)
def save_balance(body: BalanceIn, db: DbSession) -> BalanceOut:
    _get_or_404(db, Account, body.account_id)
    # One balance per account and day: typing it again replaces it.
    balance = db.scalar(
        select(Balance).where(Balance.account_id == body.account_id, Balance.day == body.day)
    )
    if balance is None:
        balance = Balance(account_id=body.account_id, day=body.day)
        db.add(balance)
    balance.amount_cents = body.amount_cents
    balance.note = body.note.strip() if body.note else None
    balance.created_at = datetime.now(UTC)
    db.commit()
    logger.info("finances: balance saved")
    return BalanceOut.model_validate(balance)


@router.delete("/balances/{balance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_balance(balance_id: int, db: DbSession) -> Response:
    db.delete(_get_or_404(db, Balance, balance_id))
    db.commit()
    logger.info("finances: balance deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_account(account_id: int, body: AccountIn, db: DbSession) -> Response:
    account = _get_or_404(db, Account, account_id)
    account.label = body.label.strip()
    account.ceiling_cents = body.ceiling_cents
    account.closes_on = body.closes_on
    db.commit()
    logger.info("finances: account updated")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/rates", status_code=status.HTTP_201_CREATED)
def add_rate(body: RateIn, db: DbSession) -> Response:
    db.add(Rate(**body.model_dump()))
    db.commit()
    logger.info("finances: rate added")
    return Response(status_code=status.HTTP_201_CREATED)


@router.post("/goals", status_code=status.HTTP_201_CREATED)
def add_goal(body: GoalIn, db: DbSession) -> Response:
    if body.account_id is not None:
        _get_or_404(db, Account, body.account_id)
    db.add(Goal(**body.model_dump(), created_at=datetime.now(UTC)))
    db.commit()
    logger.info("finances: goal added")
    return Response(status_code=status.HTTP_201_CREATED)


@router.put("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_goal(goal_id: int, body: GoalIn, db: DbSession) -> Response:
    goal = _get_or_404(db, Goal, goal_id)
    if body.account_id is not None:
        _get_or_404(db, Account, body.account_id)
    for field, value in body.model_dump().items():
        setattr(goal, field, value)
    db.commit()
    logger.info("finances: goal updated")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, db: DbSession) -> Response:
    db.delete(_get_or_404(db, Goal, goal_id))
    db.commit()
    logger.info("finances: goal deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
