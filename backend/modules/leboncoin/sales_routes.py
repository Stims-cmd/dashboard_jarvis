"""API of the sale assistant (items the owner sells), under /api/modules/leboncoin/items.

Jarvis never publishes: it stores the owner's items and prepares texts.
Logs record actions and ids only, never prices nor texts.
"""

import logging
import re
from datetime import UTC, date, datetime
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.deps import AppSettings, DbSession
from app.llm import LlmClient
from modules.leboncoin import sales
from modules.leboncoin.models import Ad, Item

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/items")

MAX_CENTS = 10_000_000  # 100 000 €
MAX_KEYWORDS = 5
COMPARABLES_SHOWN = 10

DRAFT_SYSTEM = """Tu rédiges des annonces Leboncoin en français pour un particulier.
Règles :
- utilise uniquement les informations fournies, n'invente aucune caractéristique ;
- ton simple et honnête, mentionne clairement les défauts indiqués ;
- pas d'emoji, pas de majuscules criardes, aucune coordonnée ;
- ne répète pas le prix dans la description.
Réponds exactement au format suivant, sans rien d'autre :
TITRE: <titre de 70 caractères maximum>

<description de 4 à 12 lignes>"""


def get_llm(db: DbSession, settings: AppSettings) -> LlmClient:
    return LlmClient(settings, db)


Llm = Annotated[LlmClient, Depends(get_llm)]


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


class ComparableOut(BaseModel):
    title: str
    price_cents: int | None
    location: str
    url: str
    first_seen_at: datetime


class ComparablesOut(BaseModel):
    keywords: list[str]
    count: int
    min_cents: int | None
    median_cents: int | None
    max_cents: int | None
    ads: list[ComparableOut]


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


def _like_escape(word: str) -> str:
    """The word is matched literally: % and _ are not wildcards."""
    return word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/{item_id}/comparables")
def comparables(item_id: int, db: DbSession) -> ComparablesOut:
    """Ads collected from the alerts whose title contains every keyword of the item."""
    item = _get_or_404(db, item_id)
    words = [w for w in item.keywords.lower().split() if len(w) >= 2][:MAX_KEYWORDS]
    if not words:
        return ComparablesOut(keywords=[], **sales.comparables_stats([]).__dict__, ads=[])
    query = select(Ad)
    # Parameterized LIKE. SQLite ignores case for ASCII letters only: "VÉLO" != "vélo".
    for word in words:
        query = query.where(Ad.title.ilike(f"%{_like_escape(word)}%", escape="\\"))
    found = db.scalars(query.order_by(Ad.first_seen_at.desc())).all()
    stats = sales.comparables_stats([a.price_cents for a in found if a.price_cents is not None])
    return ComparablesOut(
        keywords=words,
        **stats.__dict__,
        ads=[
            ComparableOut(
                title=a.title,
                price_cents=a.price_cents,
                location=a.location,
                url=a.url,
                first_seen_at=a.first_seen_at.replace(tzinfo=UTC)
                if a.first_seen_at.tzinfo is None
                else a.first_seen_at,
            )
            for a in found[:COMPARABLES_SHOWN]
        ],
    )


def draft_prompt(item: Item) -> str:
    """Only the item description, with contact details removed: nothing personal."""
    notes = sales.redact(item.notes).strip() or "(aucune)"
    return (
        f"Objet : {sales.redact(item.title)}\n"
        f"État : {sales.CONDITION_LABELS.get(item.condition, item.condition)}\n"
        f"Prix demandé : {sales.euros(item.asking_price_cents)}\n"
        f"Notes du vendeur :\n{notes}"
    )


def parse_draft(text: str) -> tuple[str, str] | None:
    """(title, body) from Claude's answer, or None if it does not follow the format."""
    head, _, body = text.strip().partition("\n")
    match = re.match(r"titre\s*:\s*(.*)$", head.strip(), re.IGNORECASE)
    if match is None or not match.group(1).strip() or not body.strip():
        return None
    return match.group(1).strip()[:100], body.strip()


@router.post("/{item_id}/draft")
def write_draft(item_id: int, db: DbSession, llm: Llm) -> ItemOut:
    """Prepares the ad text. The owner reviews, copies and publishes it: Jarvis never does."""
    item = _get_or_404(db, item_id)
    draft = None
    if llm.enabled:
        answer = llm.complete("leboncoin.draft", DRAFT_SYSTEM, draft_prompt(item), max_tokens=1500)
        draft = parse_draft(answer) if answer else None
    if draft is not None:
        item.draft_source = "claude"
    else:
        draft = sales.template_draft(
            item.title, item.condition, item.notes, item.asking_price_cents
        )
        item.draft_source = "template"
    item.draft_title, item.draft_body = draft
    item.updated_at = datetime.now(UTC)
    db.commit()
    logger.info("leboncoin: draft for item %d (%s)", item.id, item.draft_source)
    return _out(item)
