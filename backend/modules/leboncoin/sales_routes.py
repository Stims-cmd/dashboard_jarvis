"""API of the sale assistant (items the owner sells), under /api/modules/leboncoin/items.

Jarvis never publishes: it stores the owner's items and prepares texts.
Logs record actions and ids only, never prices nor texts.
"""

import logging
from datetime import UTC, date, datetime
from typing import Literal, Self

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.deps import DbSession
from modules.leboncoin import sales
from modules.leboncoin.models import Item

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/items")

MAX_CENTS = 10_000_000  # 100 000 €


class ItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    condition: Literal["neuf", "tres_bon", "bon", "correct", "pieces"]
    notes: str = Field(default="", max_length=2000)
    keywords: str = Field(default="", max_length=200)
    asking_price_cents: int = Field(ge=0, le=MAX_CENTS)
    floor_price_cents: int | None = Field(default=None, ge=0, le=MAX_CENTS)
    status: Literal["draft", "listed", "sold", "withdrawn"] = "draft"
    listed_on: date | None = None
    lower_after_days: int = Field(default=14, ge=1, le=365)

    @model_validator(mode="after")
    def check_prices(self) -> Self:
        if self.floor_price_cents is not None and self.floor_price_cents > self.asking_price_cents:
            raise ValueError("floor price above asking price")
        if self.listed_on is not None and self.listed_on > datetime.now(UTC).date():
            raise ValueError("listing date in the future")
        return self


class ReminderOut(BaseModel):
    due: bool
    since: date
    suggested_cents: int | None
    at_floor: bool


class ItemOut(BaseModel):
    id: int
    title: str
    condition: str
    notes: str
    keywords: str
    asking_price_cents: int
    floor_price_cents: int | None
    status: str
    listed_on: date | None
    lower_after_days: int
    price_history: list[tuple[str, int]]
    draft_title: str | None
    draft_body: str | None
    draft_source: str | None
    reminder: ReminderOut | None
    updated_at: datetime


def _today() -> date:
    return datetime.now(UTC).date()


def _get_or_404(db: DbSession, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return item


def _out(item: Item) -> ItemOut:
    reminder = sales.price_reminder(
        status=item.status,
        listed_on=item.listed_on,
        asking_cents=item.asking_price_cents,
        floor_cents=item.floor_price_cents,
        lower_after_days=item.lower_after_days,
        price_history=item.price_history,
        today=_today(),
    )
    updated_at = item.updated_at
    if updated_at.tzinfo is None:  # SQLite does not keep timezone info: stored values are UTC
        updated_at = updated_at.replace(tzinfo=UTC)
    return ItemOut(
        id=item.id,
        title=item.title,
        condition=item.condition,
        notes=item.notes,
        keywords=item.keywords,
        asking_price_cents=item.asking_price_cents,
        floor_price_cents=item.floor_price_cents,
        status=item.status,
        listed_on=item.listed_on,
        lower_after_days=item.lower_after_days,
        price_history=item.price_history,
        draft_title=item.draft_title,
        draft_body=item.draft_body,
        draft_source=item.draft_source,
        reminder=ReminderOut(**reminder.__dict__) if reminder else None,
        updated_at=updated_at,
    )


def _apply(item: Item, data: ItemIn) -> None:
    if data.asking_price_cents != item.asking_price_cents:
        # A new list is assigned: SQLAlchemy does not see in-place JSON changes.
        entry = [_today().isoformat(), data.asking_price_cents]
        item.price_history = [*(item.price_history or []), entry]
    for field, value in data.model_dump().items():
        setattr(item, field, value)
    if item.status == "listed" and item.listed_on is None:
        item.listed_on = _today()
    item.updated_at = datetime.now(UTC)


@router.get("")
def list_items(db: DbSession) -> list[ItemOut]:
    # Items still for sale first, then the most recently changed.
    items = db.scalars(select(Item).order_by(Item.updated_at.desc())).all()
    active = ("listed", "draft")
    return [_out(i) for i in sorted(items, key=lambda i: i.status not in active)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_item(data: ItemIn, db: DbSession) -> ItemOut:
    item = Item(price_history=[], created_at=datetime.now(UTC))
    _apply(item, data)  # no price yet: the first price starts the history
    db.add(item)
    db.commit()
    logger.info("leboncoin: item %d created", item.id)
    return _out(item)


@router.put("/{item_id}")
def update_item(item_id: int, data: ItemIn, db: DbSession) -> ItemOut:
    item = _get_or_404(db, item_id)
    _apply(item, data)
    db.commit()
    logger.info("leboncoin: item %d updated", item.id)
    return _out(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: DbSession) -> Response:
    db.delete(_get_or_404(db, item_id))
    db.commit()
    logger.info("leboncoin: item %d deleted", item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
